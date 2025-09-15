-- Schema for PostgresObjectStore
CREATE TABLE vrs_objects (
    vrs_id TEXT PRIMARY KEY,
    vrs_object JSONB
);

-- Schema for PostgresAnnotationObjectStore
CREATE TABLE annotations (
    object_id TEXT,
    annotation_type TEXT,
    annotation JSONB
);

CREATE INDEX idx_annotations_object_id_annotation_type
ON annotations (object_id, annotation_type);
