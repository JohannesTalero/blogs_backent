-- Insertar proyecto piloto
INSERT INTO projects (id, name, slug)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'JohannesTa',
    'johannesta'
);

-- Insertar owner
-- IMPORTANTE: reemplazar SEED_ADMIN_HASHED_PASSWORD con el hash real de .env antes de ejecutar
INSERT INTO admins (project_id, email, hashed_password, role)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'admin@johannesta.com',
    'SEED_ADMIN_HASHED_PASSWORD',
    'owner'
);

-- Insertar secciones vacías iniciales
INSERT INTO sections (project_id, type, content_json) VALUES
    ('00000000-0000-0000-0000-000000000001', 'perfil', '{"name": "Johannes", "bio": "", "photo_url": null}'),
    ('00000000-0000-0000-0000-000000000001', 'toolkit', '{"tools": []}'),
    ('00000000-0000-0000-0000-000000000001', 'recomendaciones', '{"items": []}'),
    ('00000000-0000-0000-0000-000000000001', 'contacto', '{"email": "", "linkedin": null, "twitter": null}');
