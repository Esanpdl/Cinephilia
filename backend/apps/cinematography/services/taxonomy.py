TECHNIQUES = [
    ('monochrome', 'Monochrome image', 'Color', 'An image built from tones with little or no color variation. A trailer sample alone does not establish the color format of the entire film.', True),
    ('saturated-color', 'Saturated color', 'Color', 'Strong color intensity in the sampled image; measured in HSV color space.', True),
    ('muted-color', 'Muted color', 'Color', 'Subdued color intensity in the sampled image, distinct from an entirely monochrome image.', True),
    ('tonal-contrast', 'Strong tonal contrast', 'Lighting', 'A wide separation between the darker and lighter pixels of the image. This does not identify the lighting setup.', True),
    ('silhouette', 'Silhouette', 'Lighting', 'A subject appears primarily as a dark shape against a brighter background. Requires visual review.', False),
    ('low-key-lighting', 'Low-key lighting', 'Lighting', 'Selective illumination and substantial shadow shape the scene. Darkness alone is insufficient evidence.', False),
    ('symmetry', 'Symmetrical framing', 'Composition', 'Subjects or architectural forms are arranged with visible balance around a central axis.', False),
    ('negative-space', 'Negative space', 'Composition', 'Open areas around a subject play a prominent part in the composition.', False),
    ('frame-within-frame', 'Frame within a frame', 'Composition', 'A doorway, window or another foreground shape visibly frames a subject inside the image.', False),
    ('deep-staging', 'Deep staging', 'Composition', 'Significant subjects or action occupy multiple visible depth planes. This does not establish lens or aperture settings.', False),
    ('close-up', 'Close-up', 'Framing', 'A face or detail fills much of the frame, directing attention to a limited subject.', False),
    ('wide-framing', 'Wide framing', 'Framing', 'The environment occupies a large part of the image relative to its subjects.', False),
]
