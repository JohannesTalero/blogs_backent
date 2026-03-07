#!/usr/bin/env python3
"""
Diagnóstico de login: comprueba si el admin existe en la misma DB que usa el backend
y si la contraseña coincide con el hash guardado.

Ejecutar desde la raíz del backend (mismo entorno con el que corres uvicorn):

  cd blogs_backend
  uv run python scripts/check_admin_login.py

  # o, si usas venv:
  source .venv/bin/activate   # Linux/Mac
  python scripts/check_admin_login.py
"""
import sys
import os

# Asegurar que se carga el .env y los módulos del backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext
from app.database import supabase

EMAIL = "admin@johannesta.com"
PASSWORD = "Johannesta1"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def main():
    print(f"Consultando Supabase (misma conexión que el backend) por email: {EMAIL!r}")
    print()

    result = supabase.table("admins").select("id, email, role, hashed_password").eq("email", EMAIL).execute()

    if not result.data:
        print("❌ No hay ningún admin con ese email en la base de datos.")
        print("   El backend usa la conexión de tu .env (SUPABASE_URL / SUPABASE_SERVICE_KEY).")
        print("   Comprueba que estés editando el mismo proyecto en Supabase.")
        return 1

    admin = result.data[0]
    stored_hash = admin.get("hashed_password") or ""

    print(f"✅ Admin encontrado: id={admin['id']}, email={admin['email']}, role={admin['role']}")
    print(f"   Hash en DB (primeros 20 chars): {stored_hash[:20]}...")
    print()

    if not stored_hash or stored_hash == "SEED_ADMIN_HASHED_PASSWORD":
        print("❌ El hash no está configurado (vacío o sigue el placeholder del seed).")
        print("   Actualiza hashed_password en Supabase con un hash bcrypt válido.")
        return 1

    ok = pwd_context.verify(PASSWORD, stored_hash)
    if ok:
        print(f"✅ La contraseña {PASSWORD!r} coincide con el hash guardado.")
        print("   Si el login en la web sigue fallando, revisa:")
        print("   - Que el frontend use VITE_API_URL apuntando a este backend.")
        print("   - Que no haya espacios/cambio de línea al pegar el hash en Supabase.")
    else:
        print(f"❌ La contraseña {PASSWORD!r} NO coincide con el hash guardado.")
        print("   Sustituye hashed_password en Supabase por este hash (para contraseña Johannesta1):")
        new_hash = pwd_context.hash(PASSWORD)
        print(f"   {new_hash}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
