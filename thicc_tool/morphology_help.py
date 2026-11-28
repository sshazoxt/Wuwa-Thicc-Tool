"""End-user help for existing Morphology settings, without changing their values."""
HELP = {
 'hips': ('Hips / Width (X)', 'In ADS, increases the side-to-side width of the hips using the adaptive longitudinal profile. Depth is controlled separately. In Legacy, this controls the combined hip contribution. Zero disables this contribution; 1 is the base intensity, not a 100% increase in body width. High values may cause clipping.'),
 'hips_y': ('Hips Depth (Y)', 'ADS only. Controls front-to-back expansion of the hips independently from Width. Zero disables this depth contribution. It is an intensity, not a distance in centimetres.'),
 'butt': ('Glutes', 'Increases the existing posterior gluteal volume field. This affects the rear contour and may also increase lateral volume. It does not move the pelvis bone or change leg length. Zero disables the field.'),
 'thighs': ('Thighs / Width (X)', 'In ADS, increases lateral thigh volume with a separate adaptive profile; inward expansion is limited by the original clearance function. Depth is independent. In Legacy, this controls the combined thigh contribution. Zero disables this field.'),
 'thighs_y': ('Thighs Depth (Y)', 'ADS only. Increases front-to-back thigh volume independently of lateral Width, with the original anatomical blending into the pelvis. Zero disables this depth contribution.'),
 'calves': ('Calves', 'Controls the existing lower-leg volume field around each leg axis. Zero disables the calf contribution. This does not lengthen the legs.'),
 'belly': ('Belly', 'Controls anterior abdominal expansion. Basic mode derives Depth, Width, Height and Offset together from this amount. Zero disables the belly field. Advanced mode lets you control them independently.'),
 'depth': ('Belly — Depth', 'Controls the forward displacement as a fraction of the local front-to-back half-depth of the body section. Zero disables Belly; 1 is the maximum input coefficient, not a guarantee of doubling the abdomen. Actual expansion is weighted by the field and geometry validation.'),
 'width': ('Belly — Width', 'Controls how broadly the anterior belly field extends sideways. Its support is scaled by the local horizontal half-width. Larger values spread the effect toward the flanks; smaller values concentrate it near the front centre. It does not directly widen the body in X.'),
 'height': ('Belly — Height', 'Scales the vertical extent of the belly field above and below its centre. 1 keeps the reference extent; 0.5 concentrates it vertically; 1.5 spreads it over a taller area. Anatomical limits clip the extent where necessary. It does not change character height or move vertices vertically.'),
 'offset': ('Belly — Offset', 'Moves the centre of the belly field vertically. Negative moves it toward the lower abdomen; positive toward the waist. Zero retains the reference centre, located 57% of the way from crotch to detected waist. The offset is a fraction of the crotch-to-knee span: +0.10 shifts the centre upward by 10% of that span. Anatomical limits still apply.'),
 'preset': ('Base shape', 'Loads a starting combination of the basic regional intensities. These are adjustable after selection; it is not a fixed body shape.'),
 'target': ('Target strength', 'Legacy only. Scales the relative silhouette calibration target. It does not directly set a displacement in centimetres. ADS ignores this setting.'),
 'upper': ('Upper spread', 'Legacy coupled hip-thigh profile only. Controls the spread of the hip contribution toward the waist. ADS ignores this setting.'),
 'lower': ('Lower spread', 'Legacy coupled hip-thigh profile only. Controls the spread of the hip contribution toward the thighs. ADS ignores this setting.'),
 'peak': ('Peak height offset', 'Legacy coupled hip-thigh profile only. Adjusts the vertical position of the strongest hip expansion; negative is lower and positive is higher. ADS ignores this setting.'),
 'direction': ('Directional expansion', 'Scales each region’s X (width) and Y (depth) displacement contributions. 1 keeps the contribution unchanged, 0 disables it, and 2 doubles that component before later validation. Groin fill remains independent.'),
 'strength': ('Regularization — Strength', 'Controls the strength of the optional final morphological regularization. Higher values can alter more of the displacement field. This is separate from ADS curve fitting.'),
 'tolerance': ('Regularization — Noise tolerance', 'Controls the tolerance used by the optional final regularizer when evaluating local displacement irregularities. It is not a physical distance in centimetres.'),
 'relative': ('Relative silhouette calibration', 'Legacy only. Calibrates hip expansion against a relative silhouette target. ADS uses its own adaptive profiles instead.'),
 'coupled': ('Coupled hip-thigh profile', 'Legacy only. Enables the coupled hip and thigh shape controls. ADS uses the approved experiment 78 profiles instead.'),
 'arms': ('Advanced arm protection', 'Adds protection against unwanted movement of arm and hand vertices. It does not change the arm pose or prevent all in-game animation collisions.'),
 'clothing': ('Advanced clothing adaptation', 'Enables experimental clothing correction following the body deformation. It cannot guarantee that every garment remains collision-free.'),
 'inner': ('Fill inner thigh gap', 'Adds an independent contribution to fill the space between the inner thighs. Large values or combinations may create contact or overlap.'),
 'virtual': ('Morphological groin fold', 'Enables the existing groin-fold reconstruction option where supported by the active deformation path.'),
 'rounding': ('Thigh rounding', 'Enables the Legacy thigh-rounding correction. It is skipped when Direct Thighs / ADS is active. Final regularization is a separate option.'),
 'bounce': ('Bounce', 'Selects the existing bounce profile. Only Normal is implemented; this does not add a new physics simulation.'),
 'shading': ('Surface shading', 'Selects how surface normal and tangent data are preserved or recomputed after deformation. It affects lighting, not the shape itself.'),
 'field': ('Deformation field', 'Selects the existing Legacy or Continuous field behavior for supported contributions. ADS retains its own hip and thigh longitudinal profiles.'),
 'taubin': ('Taubin displacement smoothing', 'Optional experimental smoothing of the displacement field. It is not required by ADS and can change the resulting shape.'),
 'regularization': ('Final morphological regularization', 'Optional final correction for local deformation irregularities. ADS profiles are already fitted before deformation; this is an independent downstream correction.'),
}

def add_help(layout, key):
    from PySide6.QtWidgets import QToolButton, QMessageBox
    from PySide6.QtCore import Qt
    title,description=HELP[key]
    b=QToolButton(); b.setText('!'); b.setFixedSize(19,19)
    b.setStyleSheet('QToolButton { border: 1px solid palette(mid); border-radius: 9px; padding: 0px; font-weight: bold; } QToolButton:hover { border-color: palette(highlight); }')
    b.setCursor(Qt.CursorShape.PointingHandCursor); b.setToolTip(description)
    b.setAccessibleName('Help: '+title); b.clicked.connect(lambda checked=False: QMessageBox.information(b.window(),title,description))
    layout.addWidget(b)
    return b

def help_label(text,key):
    from PySide6.QtWidgets import QWidget,QHBoxLayout,QLabel
    w=QWidget(); row=QHBoxLayout(w); row.setContentsMargins(0,0,0,0); row.setSpacing(5)
    label=QLabel(text); row.addWidget(label); add_help(row,key); row.addStretch()
    return w,label

def help_widget(widget,key):
    from PySide6.QtWidgets import QWidget,QHBoxLayout
    w=QWidget(); row=QHBoxLayout(w); row.setContentsMargins(0,0,0,0); row.setSpacing(5)
    row.addWidget(widget); add_help(row,key); row.addStretch(); return w
