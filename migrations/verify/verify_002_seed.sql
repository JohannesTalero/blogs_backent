DO $$
BEGIN
    ASSERT (SELECT COUNT(*) FROM projects WHERE slug = 'johannesta') = 1,
        'Proyecto johannesta no existe';

    ASSERT (SELECT COUNT(*) FROM admins
        WHERE project_id = '00000000-0000-0000-0000-000000000001' AND role = 'owner') = 1,
        'Owner de johannesta no existe';

    ASSERT (SELECT COUNT(*) FROM sections
        WHERE project_id = '00000000-0000-0000-0000-000000000001') = 4,
        'Las 4 secciones iniciales no existen';

    ASSERT (SELECT COUNT(*) FROM sections
        WHERE project_id = '00000000-0000-0000-0000-000000000001'
        AND type IN ('perfil', 'toolkit', 'recomendaciones', 'contacto')) = 4,
        'Faltan tipos de sección';

    RAISE NOTICE 'verify_002: seed verificado correctamente';
END $$;
