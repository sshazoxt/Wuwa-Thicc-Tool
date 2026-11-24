"""Stickman from bone weights: label every bone head / torso / arm_l / arm_r / leg_l / leg_r.

Bone positions are not stored in a WWMI mod, but every vertex is skinned to
bones, so:
  * bone centroid = weighted mean of the vertices it moves;
  * two bones are connected when vertices are weighted to both (joint areas).
That graph is the character's skeleton.  The limbs are the branches of the
shortest-path tree grown from the pelvis towards the feet, hands and head.
"""
import heapq

import numpy as np



def bone_graph(P, bi, bw, min_w=0.5, triangles=None):
    nb = int(bi.max()) + 1
    W = np.zeros(nb)
    C = np.zeros((nb, 3))

    for k in range(bi.shape[1]):
        np.add.at(W, bi[:, k], bw[:, k])
        np.add.at(C, bi[:, k], bw[:, k, None] * P)

    ok = W > min_w
    C[ok] /= W[ok, None]

    adj = {}
    K = bi.shape[1]

    # 1. Conexiones por huesos que comparten un mismo vértice.
    for k1 in range(K):
        for k2 in range(k1 + 1, K):
            m = (
                (bw[:, k1] > 0.05)
                & (bw[:, k2] > 0.05)
                & (bi[:, k1] != bi[:, k2])
            )

            if not m.any():
                continue

            a = np.minimum(bi[m, k1], bi[m, k2])
            b = np.maximum(bi[m, k1], bi[m, k2])
            w = np.minimum(bw[m, k1], bw[m, k2])

            key = a * nb + b
            u, inv = np.unique(key, return_inverse=True)
            s = np.bincount(inv, weights=w)

            for kk, ss in zip(u, s):
                adj[int(kk)] = adj.get(int(kk), 0.0) + float(ss)

    # 2. Conexiones entre huesos presentes en vértices vecinos
    #    de la misma superficie triangular.
    if triangles is not None and len(triangles):
        tri = np.asarray(triangles, dtype=np.int64)

        edge_a = np.concatenate([
            tri[:, 0], tri[:, 1], tri[:, 2],
            tri[:, 1], tri[:, 2], tri[:, 0]
        ])

        edge_b = np.concatenate([
            tri[:, 1], tri[:, 2], tri[:, 0],
            tri[:, 0], tri[:, 1], tri[:, 2]
        ])

        for k1 in range(K):
            ba = bi[edge_a, k1]
            wa = bw[edge_a, k1]

            for k2 in range(K):
                bb = bi[edge_b, k2]
                wb = bw[edge_b, k2]

                m = (
                    (wa > 0.05)
                    & (wb > 0.05)
                    & (ba != bb)
                )

                if not m.any():
                    continue

                a = np.minimum(ba[m], bb[m])
                b = np.maximum(ba[m], bb[m])
                w = np.minimum(wa[m], wb[m])

                key = a * nb + b
                u, inv = np.unique(key, return_inverse=True)
                s = np.bincount(inv, weights=w)

                for kk, ss in zip(u, s):
                    adj[int(kk)] = (
                        adj.get(int(kk), 0.0) + float(ss)
                    )

    G = {int(b): [] for b in np.nonzero(ok)[0]}

    for kk, s in adj.items():
        a, b = divmod(kk, nb)

        if s > 0.5 and a in G and b in G:
            d = float(np.linalg.norm(C[a] - C[b])) + 0.5
            G[a].append((b, d))
            G[b].append((a, d))

    return W, C, ok, G



def spt(G, src):
    dist = {src: 0.0}
    par = {src: None}
    h = [(0.0, src)]
    while h:
        d, u = heapq.heappop(h)
        if d > dist[u]:
            continue
        for v, w in G[u]:
            nd = d + w
            if nd < dist.get(v, 1e18):
                dist[v] = nd
                par[v] = u
                heapq.heappush(h, (nd, v))
    return dist, par


def path(par, t):
    out = []
    while t is not None:
        out.append(t)
        t = par[t]
    return out[::-1]


def label_bones(P, bi, bw, H, vertex_mask=None, triangles=None):
    """Return (region per bone id: dict, info dict).

    vertex_mask:
        Boolean mask selecting anatomical vertices.
        Excludes hair/accessories from bone centroid and graph analysis.
    """

    
    if vertex_mask is not None:
        vertex_mask = np.asarray(vertex_mask, dtype=bool)

        if vertex_mask.shape != (len(P),):
            raise ValueError(
                "vertex_mask must have one value per mesh vertex"
            )

        if not vertex_mask.any():
            raise ValueError(
                "vertex_mask contains no anatomical vertices"
            )

        ids = np.flatnonzero(vertex_mask)

        P_graph = P[ids]
        bi_graph = bi[ids]
        bw_graph = bw[ids]

        tri_graph = None

        if triangles is not None:
            old_to_new = np.full(len(P), -1, dtype=np.int64)
            old_to_new[ids] = np.arange(len(ids))

            tri = np.asarray(triangles, dtype=np.int64)

            valid = np.all(vertex_mask[tri], axis=1)
            tri_graph = old_to_new[tri[valid]]

    else:
        P_graph = P
        bi_graph = bi
        bw_graph = bw
        tri_graph = triangles

    W, C, ok, G = bone_graph(
        P_graph,
        bi_graph,
        bw_graph,
        triangles=tri_graph
    )


    bones = np.array(sorted(G))
    c = C[bones]
    # pelvis: heavy bone near the body centre line at ~55% height
    score = -np.abs(c[:, 2] - 0.55 * H) - 2.0 * np.abs(c[:, 0]) - np.abs(c[:, 1]) + 0.002 * W[bones]
    pelvis = int(bones[np.argmax(score)])
    dist, par = spt(G, pelvis)
    reach = np.array([b in dist for b in bones])
    
    
    # Diagnostic: graph connectivity and upper bone candidates.
    unseen = set(G)
    components = []

    while unseen:
        start = unseen.pop()
        stack = [start]
        group = [start]

        while stack:
            u = stack.pop()

            for v, _ in G[u]:
                if v in unseen:
                    unseen.remove(v)
                    stack.append(v)
                    group.append(v)

        components.append(group)

    components.sort(key=len, reverse=True)

    print("\n===== MESH SKELETON CONNECTIVITY =====")
    print("Graph bones:", len(G))
    print("Connected components:", len(components))

    for i, group in enumerate(components[:10]):
        ids = np.asarray(group, dtype=int)
        top = ids[np.argmax(C[ids, 2])]

        print(
            f"Component {i}: bones={len(group)} "
            f"top_bone={top} "
            f"top_xyz={C[top].round(2)} "
            f"pelvis_connected={pelvis in group}"
        )

    top_ids = np.argsort(C[bones, 2])[-20:][::-1]

    print("\nTop 20 bone centroids:")

    for j in top_ids:
        b = int(bones[j])

        print(
            f"bone={b:4d} "
            f"XYZ={C[b].round(2)} "
            f"weight={W[b]:.1f} "
            f"degree={len(G[b])} "
            f"reachable={b in dist}"
        )

    print("===== END CONNECTIVITY =====\n")


    def best(mask, s):
        idx = np.nonzero(mask & reach)[0]
        return int(bones[idx[np.argmax(s[idx])]]) if len(idx) else None

    side_r, side_l = c[:, 0] > 1.0, c[:, 0] < -1.0
    low = c[:, 2] < 0.25 * H
    foot_r = best(side_r & low, -c[:, 2])
    foot_l = best(side_l & low, -c[:, 2])
    head = best(c[:, 2] > 0.80 * H, c[:, 2] - 2.0 * np.abs(c[:, 0]))
    # hands: farthest (graph distance) bones on each side, between hip and chest height
    gd = np.array([dist.get(int(b), -1.0) for b in bones])
    mid = (c[:, 2] > 0.30 * H) & (c[:, 2] < 0.80 * H) & (np.abs(c[:, 0]) > 0.10 * H)
    hand_r = best(side_r & mid, gd + 0.5 * np.abs(c[:, 0]))
    hand_l = best(side_l & mid, gd + 0.5 * np.abs(c[:, 0]))

    
    seeds = dict(
        pelvis=pelvis,
        foot_r=foot_r,
        foot_l=foot_l,
        head=head,
        hand_r=hand_r,
        hand_l=hand_l,
    )

    paths = {
        k: path(par, v)
        for k, v in seeds.items()
        if v is not None and k != "pelvis"
    }

    # Refine pelvis from the shared path of both leg branches.
    pelvis_initial = pelvis
    pelvis_candidate = None
    pelvis_method = "initial_heuristic"

    if "foot_r" in paths and "foot_l" in paths:
        pr = paths["foot_r"]
        pl = paths["foot_l"]

        common = []
        for a, b in zip(pr, pl):
            if a != b:
                break
            common.append(a)

        if common:
            candidate = int(common[-1])
            cp = C[candidate]

            # Structural and geometric validation.
            centered = abs(cp[0]) < max(1.0, 0.12 * H)
            below_initial = cp[2] < C[pelvis_initial, 2]
            above_feet = (
                cp[2] > max(C[foot_r, 2], C[foot_l, 2])
            )

            if centered and below_initial and above_feet:
                pelvis_candidate = candidate
                pelvis = candidate
                pelvis_method = "shared_leg_branch"

                # Rebuild the shortest-path tree from the refined pelvis.
                dist, par = spt(G, pelvis)
                reach = np.array([int(b) in dist for b in bones])

                seeds["pelvis"] = pelvis
                paths = {
                    k: path(par, v)
                    for k, v in seeds.items()
                    if v is not None and k != "pelvis"
                }

    seeds["pelvis"] = pelvis

    region = {}


    # Identificar el último hueso compartido por ambas piernas.
    right = paths.get("foot_r", [])
    left = paths.get("foot_l", [])

    common = []
    for br, bl in zip(right, left):
        if br != bl:
            break
        common.append(br)

    pelvis_branch = common[-1] if common else None

    right_start = (
        right[len(common)]
        if len(right) > len(common) else None
    )

    left_start = (
        left[len(common)]
        if len(left) > len(common) else None
    )

    print("\n===== PELVIS / LEG BRANCH DIAGNOSTIC =====")
    print("Selected pelvis:", pelvis)
    print("Common path:", common)
    print("Last common bone:", pelvis_branch)
    print("Right leg start:", right_start)
    print("Left leg start:", left_start)

    for b in common:
        print(
            f"  common {b}: "
            f"XYZ={C[b].round(2)} "
            f"Z/H={C[b, 2] / H:.3f}"
        )

    for name, b in (
        ("right", right_start),
        ("left", left_start),
    ):
        if b is not None:
            print(
                f"  {name} start {b}: "
                f"XYZ={C[b].round(2)} "
                f"Z/H={C[b, 2] / H:.3f}"
            )

    print("===== END BRANCH DIAGNOSTIC =====\n")
    region = {}

    def branch(own, others):
        o = set()
        for p in others:
            o |= set(p)
        return [b for b in own if b not in o]
    
        # Diagnostic: inspect why the head branch may be empty.
    print("\n===== HEAD PATH DIAGNOSTIC =====")
    print(f"H={H:.2f}")
    print(f"Head seed threshold={0.80 * H:.2f}")
    print(f"Head region threshold={0.78 * H:.2f}")
    print("Seeds:", seeds)

    # All reachable bones high enough to be head candidates.
    head_candidates = [
        int(b) for b in bones
        if int(b) in dist and C[int(b), 2] > 0.80 * H
    ]

    head_candidates.sort(
        key=lambda b: C[b, 2],
        reverse=True
    )

    print("\nReachable head candidates:")

    for b in head_candidates:
        print(
            f"  bone={b:4d} "
            f"XYZ={C[b].round(2)} "
            f"weight={W[b]:.1f} "
            f"degree={len(G[b])}"
        )

    # Inspect head and arm paths.
    for key in ("head", "hand_r", "hand_l"):
        if key in paths:
            p = paths[key]
            print(f"\n{key}: length={len(p)}")
            print("  path:", p)
            print(
                "  high bones:",
                [b for b in p if C[b, 2] > 0.78 * H]
            )
        else:
            print(f"\n{key}: NO PATH")

    # Reproduce the exact head-branch filtering.
    head_path = paths.get("head", [])
    arm_paths = [
        paths[k]
        for k in ("hand_r", "hand_l")
        if k in paths
    ]

    arm_union = set()
    for p in arm_paths:
        arm_union.update(p)

    head_overlap = sorted(set(head_path) & arm_union)
    head_remaining = [
        b for b in head_path
        if b not in arm_union
    ]

    head_above_threshold = [
        b for b in head_remaining
        if C[b, 2] > 0.78 * H
    ]

    print("\nHead/arm overlap:", head_overlap)
    print("Head branch remaining:", head_remaining)
    print("Head branch above threshold:", head_above_threshold)

    print("===== END HEAD PATH DIAGNOSTIC =====\n")

    
    # Track the origin of every bone label without changing classification.
    region = {}
    region_origin = {}

    def set_direct(b, label, rule):
        b = int(b)
        region[b] = label
        region_origin[b] = {
            "stage": "direct",
            "rule": rule,
        }

    # Direct leg classification.
    if "foot_r" in paths and "foot_l" in paths:
        for b in branch(paths["foot_r"], [paths["foot_l"]]):
            set_direct(b, "leg_r", "right_leg_branch")

        for b in branch(paths["foot_l"], [paths["foot_r"]]):
            set_direct(b, "leg_l", "left_leg_branch")

    # Classify the arm branches first.
    if "hand_r" in paths:
        arm_r = branch(
            paths["hand_r"],
            [
                paths[k]
                for k in ("hand_l", "head")
                if k in paths
            ]
        )

        for b in arm_r:
            set_direct(b, "arm_r", "right_arm_branch")

    if "hand_l" in paths:
        arm_l = branch(
            paths["hand_l"],
            [
                paths[k]
                for k in ("hand_r", "head")
                if k in paths
            ]
        )

        for b in arm_l:
            set_direct(b, "arm_l", "left_arm_branch")

    # Direct head candidates: preserve the current rule.
    arm_bones = {
        b for b, label in region.items()
        if label in ("arm_r", "arm_l")
    }

    if "head" in paths:
        head_candidates = [
            int(b)
            for b in bones
            if int(b) in dist
            and C[int(b), 2] > 0.78 * H
            and int(b) not in arm_bones
        ]

        for b in head_candidates:
            set_direct(b, "head", "reachable_height_candidate")

    # Inherit the nearest labelled ancestor in the pelvis tree.
    for b in bones:
        b = int(b)

        if b in region:
            continue

        if b not in dist:
            continue

        t = par[b]
        chain = [b]

        while t is not None and t not in region:
            chain.append(t)
            t = par[t]

        lab = region.get(t, "torso") if t is not None else "torso"

        for depth, x in enumerate(chain, start=1):
            if x not in region:
                region[x] = lab
                region_origin[x] = {
                    "stage": "ancestor" if t is not None else "default_torso",
                    "source_bone": int(t) if t is not None else None,
                    "depth": depth,
                }

    # Unreachable bones: preserve nearest labelled centroid assignment.
    lab_b = np.array([b for b in region])

    for b in bones:
        b = int(b)

        if b not in region:
            distances = np.linalg.norm(C[lab_b] - C[b], axis=1)
            j = int(np.argmin(distances))
            source = int(lab_b[j])

            region[b] = region[source]
            region_origin[b] = {
                "stage": "proximity",
                "source_bone": source,
                "distance": float(distances[j]),
            }

    # Provenance diagnostic.
    print("\n===== CLASSIFICATION PROVENANCE =====")

    stages = ("direct", "ancestor", "default_torso", "proximity")

    for label in ("head", "torso", "arm_l", "arm_r", "leg_l", "leg_r"):
        ids = sorted(
            b for b, r in region.items()
            if r == label
        )

        if not ids:
            continue

        print(f"\n{label}: {len(ids)} bones")

        for stage in stages:
            count = sum(
                region_origin.get(b, {}).get("stage") == stage
                for b in ids
            )
            if count:
                print(f"  {stage}: {count}")

        # Show every head bone with its classification origin.
        if label == "head":
            print("  -- bone details --")

            for b in sorted(ids, key=lambda k: C[k, 2], reverse=True):
                src = region_origin.get(b, {})
                stage = src.get("stage", "unknown")

                if stage == "direct":
                    detail = src.get("rule", "")
                elif stage == "ancestor":
                    detail = (
                        f"ancestor={src.get('source_bone')} "
                        f"depth={src.get('depth')}"
                    )
                elif stage == "proximity":
                    detail = (
                        f"nearest={src.get('source_bone')} "
                        f"distance={src.get('distance', 0):.2f}"
                    )
                else:
                    detail = ""

                parent = par.get(b)

                if parent is not None:
                    parent_info = (
                        f"parent={parent} "
                        f"parent_XYZ={C[parent].round(2)}"
                    )
                else:
                    parent_info = "parent=None"

                print(
                    f"    bone={b:3d} "
                    f"XYZ={C[b].round(2)} "
                    f"weight={W[b]:.1f} "
                    f"reachable={b in dist} "
                    f"{parent_info} "
                    f"origin={stage} {detail}"
                )

    print("\n===== END CLASSIFICATION PROVENANCE =====")



    print("\n===== END HEAD / TORSO CLASSIFICATION =====")
    
    return region, dict(
        seeds=seeds,
        centroid=C,
        weight=W,
        height=float(H),
        paths=paths,
        pelvis_initial=pelvis_initial,
        pelvis_candidate=pelvis_candidate,
        pelvis_method=pelvis_method,
    )



def region_weights(bi, bw, region):
    """Per-vertex weight on each region."""
    names = ("head", "torso", "arm_l", "arm_r", "leg_l", "leg_r")
    nb = int(bi.max()) + 1
    lut = {n: np.zeros(nb) for n in names}
    for b, r in region.items():
        lut[r][b] = 1.0
    return {n: (lut[n][bi] * bw).sum(1) for n in names}
    

def print_anatomy_report(sinfo, region):
    """
    Read-only anatomical report.
    Shows the actual bone chains from pelvis to each foot.
    No deformation and no assumed knee positions.
    """
    C = sinfo["centroid"]
    W = sinfo["weight"]
    H = float(sinfo["height"])
    paths = sinfo["paths"]

    print("\n========== ANATOMY STRUCTURE ==========")

    for side, key in (
        ("RIGHT", "foot_r"),
        ("LEFT", "foot_l"),
    ):
        if key not in paths:
            print(f"\n{side}: no connected foot path")
            continue

        chain = paths[key]
        cumulative = 0.0

        print(f"\n--- {side} LEG CHAIN ---")
        print(f"bones in path: {len(chain)}")
        print(
            " id       X        Y        Z"
            "    Z/H      SEGMENT    LENGTH"
        )

        previous = None

        for bone in chain:
            point = C[bone]

            if previous is not None:
                segment = float(
                    np.linalg.norm(point - previous)
                )
                cumulative += segment
            else:
                segment = 0.0

            label = region.get(bone, "unknown")

            print(
                f"{bone:4d} "
                f"{point[0]:8.2f} "
                f"{point[1]:8.2f} "
                f"{point[2]:8.2f} "
                f"{point[2] / H:7.3f} "
                f"{label:10s} "
                f"{cumulative:8.2f}"
            )

            previous = point

        print(f"Total centroid-chain length: {cumulative:.2f} cm")

    print("\n========== END ANATOMY STRUCTURE ==========\n")

