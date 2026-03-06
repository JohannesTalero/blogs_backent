DO $$
BEGIN
    -- projects
    ASSERT (SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'projects' AND column_name IN ('id','name','slug','created_at')) = 4,
        'Tabla projects: faltan columnas';

    -- admins
    ASSERT (SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'admins' AND column_name IN ('id','project_id','email','hashed_password','role','created_at')) = 6,
        'Tabla admins: faltan columnas';

    -- sections
    ASSERT (SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'sections' AND column_name IN ('id','project_id','type','content_json','updated_at')) = 5,
        'Tabla sections: faltan columnas';

    -- blocks
    ASSERT (SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = 'blocks' AND column_name IN ('id','project_id','type','content_json','order','visible','created_at')) = 7,
        'Tabla blocks: faltan columnas';

    -- RLS habilitado en las 4 tablas
    ASSERT (SELECT COUNT(*) FROM pg_tables
        WHERE tablename IN ('projects','admins','sections','blocks') AND rowsecurity = true) = 4,
        'RLS no está habilitado en todas las tablas';

    -- CHECK constraint en admins.role rechaza valores inválidos
    BEGIN
        INSERT INTO admins (project_id, email, hashed_password, role)
        VALUES (gen_random_uuid(), 'test@test.com', 'hash', 'superadmin');
        ASSERT false, 'Debería haber fallado: rol inválido';
    EXCEPTION WHEN check_violation THEN
        NULL; -- Correcto
    END;

    RAISE NOTICE 'verify_001: todos los checks pasaron';
END $$;
