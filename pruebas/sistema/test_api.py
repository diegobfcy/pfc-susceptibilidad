"""Caja negra de S1/S2/S3 por contrato: CP-04, CP-11, CP-13, CP-15 a CP-19 y CP-21."""

from __future__ import annotations

import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from cliente_pruebas import Cliente
from sqlalchemy import text

ID_MODELO = 1
MES = {"fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30"}
MES_INFERENCIA = {**MES, "id_modelo_version": ID_MODELO}
INV, ESP, ASE = "INVESTIGADOR", "ESPECIALISTA", "ASESOR"
# Tabla de permisos (rol x endpoint). Los cuerpos inválidos no tienen efecto: el rol autorizado
# recibe 400/404/422 y el no autorizado, 403 antes de cualquier validación.
MATRIZ = [
    ("POST", "/ingestas", {INV}),
    ("GET", "/ingestas/999999", {INV, ASE}),
    ("POST", "/ingestas/999999/archivos", {INV}),
    ("POST", "/entrenamientos", {INV}),
    ("POST", "/inferencias", {INV}),
    ("GET", "/inferencias/999999", {INV, ASE}),
    ("POST", "/procesamientos/999999/cancelar", {INV}),
    ("GET", "/mapas/susceptibilidad/2023-03/7/36/66.pbf", {INV, ESP}),
    ("GET", "/consulta-punto?periodo=2023-03&lat=-7&lon=-79", {INV, ESP}),
    ("GET", "/indicadores", {INV, ASE}),
    ("GET", "/bitacora", {INV, ASE}),
    ("GET", "/procesamientos/activo", {INV, ASE}),
]


def _esperar_fin(cliente: Cliente, identificador: int, limite_s: int = 600) -> dict[str, Any]:
    t0 = time.time()
    while time.time() - t0 < limite_s:
        estado = cliente.get(f"/ingestas/{identificador}").json()
        if estado["estado"] in ("COMPLETADO", "FALLIDO", "CANCELADO", "EN_ESPERA"):
            return estado
        time.sleep(1)
    raise TimeoutError(identificador)


@pytest.mark.parametrize(("metodo", "ruta", "permitidos"), MATRIZ)
@pytest.mark.parametrize("rol", [INV, ESP, ASE])
def test_cp16_rbac(clientes: dict, rol: str, metodo: str, ruta: str, permitidos: set[str]) -> None:
    c = clientes[rol]
    if metodo == "GET":
        r = c.get(ruta)
    elif ruta.endswith("/archivos"):
        r = c.s.post(f"{c.base}{ruta}", headers=c.csrf(), files={"archivo": ("a.nc", b"CDF")})
    else:
        r = c.post(ruta, json={})
    if rol in permitidos:
        assert r.status_code not in (401, 403), r.text
    else:
        assert r.status_code == 403, r.text


@pytest.mark.parametrize(("metodo", "ruta", "_"), MATRIZ)
def test_cp16_sin_sesion_401(metodo: str, ruta: str, _: Any) -> None:
    anonimo = Cliente()
    if metodo == "GET":
        assert anonimo.get(ruta).status_code == 401
    elif ruta.endswith("/archivos"):
        r = anonimo.s.post(f"{anonimo.base}{ruta}", files={"archivo": ("a.nc", b"CDF")})
        assert r.status_code in (400, 401)  # la cabecera CSRF se exige después de la sesión
    else:
        assert anonimo.post(ruta, json={}).status_code == 401


@pytest.fixture(scope="module", autouse=True)
def _sin_procesos_en_espera(motor_bd: Any) -> None:
    """Una corrida interrumpida no debe dejar ocupado el único proceso activo permitido."""
    with motor_bd.begin() as c:
        c.execute(
            text("""UPDATE sistema.procesamiento SET estado = 'CANCELADO', finalizado_en = now()
                    WHERE estado = 'EN_ESPERA'""")
        )


def test_cp15_veinte_envios_simultaneos(clientes: dict) -> None:
    inv = clientes[INV]
    token = inv.csrf()

    def enviar(_: int) -> int:
        r = inv.s.post(f"{inv.base}/inferencias", json=MES_INFERENCIA, headers=token)
        return r.status_code

    with ThreadPoolExecutor(20) as hilos:
        codigos = list(hilos.map(enviar, range(20)))
    assert sorted(codigos) == [202] + [409] * 19, codigos
    activos = [
        f
        for f in (inv.get(f"/ingestas/{i}").json() for i in _ultimos(inv))
        if f.get("estado") in ("PENDIENTE", "EN_CURSO")
    ]
    assert len(activos) <= 1
    if activos:
        _esperar_fin(inv, activos[0]["id_procesamiento"])


def _ultimos(inv: Cliente) -> list[int]:
    eventos = inv.get("/bitacora").json()["eventos"]
    return sorted({e["id_procesamiento"] for e in eventos if e["id_procesamiento"]})[-3:]


def test_cp11_artefacto_alterado_422_sin_escribir(
    clientes: dict, motor_bd: Any, tmp_path: Path
) -> None:
    with motor_bd.connect() as c:
        original = c.execute(text("""SELECT ruta_artefacto, sha256 FROM modelo.modelo_version
                    WHERE id_modelo_version = 1""")).one()
    datos = Path(original[0]).read_bytes()
    alterado = tmp_path / "alterado.ubj"
    alterado.write_bytes(datos[:-1] + bytes([datos[-1] ^ 1]))
    alterado.chmod(0o644)
    with motor_bd.begin() as c:
        id_alterado = c.execute(
            text("""INSERT INTO modelo.modelo_version
                (algoritmo, version, estado, ruta_artefacto, sha256, hiperparametros)
                VALUES ('XGBOOST', 'alterado', 'CANDIDATA', :r, :s, '{}')
                ON CONFLICT (algoritmo, version)
                DO UPDATE SET ruta_artefacto = EXCLUDED.ruta_artefacto
                RETURNING id_modelo_version"""),
            {"r": str(alterado), "s": original[1]},
        ).scalar_one()
    inv = clientes[INV]
    r = inv.post("/inferencias", json={**MES, "id_modelo_version": id_alterado})
    assert r.status_code == 422 and "SHA-256" in r.json()["detalle"]
    eventos = inv.get("/bitacora", params={"tipo": "ERROR"}).json()["eventos"]
    assert any(e["descripcion"] == "artefacto alterado" for e in eventos)
    with motor_bd.begin() as c:
        c.execute(
            text("DELETE FROM modelo.modelo_version WHERE id_modelo_version = :i"),
            {"i": id_alterado},
        )


def test_cp11_y_cp13_inferencia_integra_reemplaza_sin_duplicar(
    clientes: dict, motor_bd: Any
) -> None:
    inv = clientes[INV]
    r = inv.post("/inferencias", json=MES_INFERENCIA)
    assert r.status_code == 202
    estado = _esperar_fin(inv, r.json()["id_procesamiento"])
    assert estado["estado"] == "COMPLETADO" and estado["resumen"]["filas"] == 108461
    with motor_bd.connect() as c:
        filas = c.execute(
            text("SELECT count(*) FROM resultado.susceptibilidad WHERE periodo = '2026-06-01'")
        ).scalar_one()
    assert filas == 108461


def test_cp13_cp12_toda_la_serie_coincide_con_sql(motor_bd: Any) -> None:
    with motor_bd.connect() as c:
        meses = c.execute(text("""SELECT periodo, count(*) FROM resultado.susceptibilidad
                    GROUP BY periodo HAVING count(*) <> 108461""")).all()
        total, n_meses = c.execute(
            text("SELECT count(*), count(DISTINCT periodo) FROM resultado.susceptibilidad")
        ).one()
        huerfanas = c.execute(text("""SELECT count(*) FROM resultado.susceptibilidad s
                    LEFT JOIN ref.celda_analisis c USING (id_celda)
                    WHERE s.periodo = '2023-03-01' AND c.id_celda IS NULL""")).scalar_one()
        diferentes = c.execute(
            text("""SELECT count(*) FROM resultado.susceptibilidad
                    WHERE nivel <> CASE WHEN probabilidad < 0.25 THEN 1
                                        WHEN probabilidad < 0.5 THEN 2
                                        WHEN probabilidad < 0.75 THEN 3 ELSE 4 END""")
        ).scalar_one()
    assert meses == [] and (total, n_meses) == (34382137, 317)
    assert huerfanas == 0 and diferentes == 0


def _crear_en_espera(motor_bd: Any) -> int:
    with motor_bd.begin() as c:
        return c.execute(text("""INSERT INTO sistema.procesamiento
                (id_usuario, tipo, fecha_desde, fecha_hasta, zona, estado)
                SELECT id_usuario, 'INGESTA', '2026-01-01', '2026-01-31',
                       ST_Multi(ST_MakeEnvelope(-81, -10, -77, -4, 4326)), 'EN_ESPERA'
                FROM sistema.usuario WHERE correo = 'inv@pruebas.pfc'
                RETURNING id_procesamiento""")).scalar_one()


def test_cp04_carga_manual_real(clientes: dict, motor_bd: Any, tmp_path: Path) -> None:
    inv = clientes[INV]
    identificador = _crear_en_espera(motor_bd)
    ruta = f"{inv.base}/ingestas/{identificador}/archivos"

    def subir(nombre: str, contenido: Any, fuente: str = "dem_glo30") -> Any:
        return inv.s.post(
            ruta,
            headers=inv.csrf(),
            data={"fuente": fuente},
            files={"archivo": (nombre, contenido)},
        )

    assert subir("malware.exe", b"MZ\x90").status_code == 415
    assert subir("falso.nc", b"MZ\x90").status_code == 415
    # Archivo real de más de 2 GB (disperso): atraviesa nginx y se rechaza por tamaño.
    grande = tmp_path / "grande.nc"
    with grande.open("wb") as f:
        f.truncate(2 * 1024**3 + 1024)
    with grande.open("rb") as f:
        r = inv.s.post(
            ruta,
            headers={**inv.csrf(), "Content-Type": "application/octet-stream"},
            data=f,
        )
    assert r.status_code == 422, r.text
    valido = b"CDF\x01" + b"\x00" * 64 * 1024  # mayor que el límite general de 16 KB
    r = subir("prueba_cp04.nc", valido)
    assert r.status_code == 201, r.text
    assert len(r.json()["sha256"]) == 64
    estado = inv.get(f"/ingestas/{identificador}").json()["estado"]
    assert estado in ("PENDIENTE", "EN_CURSO", "EN_ESPERA", "COMPLETADO")  # volvió a la cola
    with motor_bd.connect() as c:
        registrado = (
            c.execute(
                text("SELECT DISTINCT origen FROM sistema.dataset WHERE sha256 = :s"),
                {"s": r.json()["sha256"]},
            )
            .scalars()
            .all()
        )  # el mismo archivo pudo cargarse en corridas anteriores
    assert registrado == ["MANUAL"]
    final = _esperar_fin(inv, identificador, 900)
    if final["estado"] == "EN_ESPERA":
        assert inv.post(f"/procesamientos/{identificador}/cancelar").status_code == 204


def test_cp17_cookie_y_hash(motor_bd: Any) -> None:
    c = Cliente()
    r = c.entrar("ASESOR")
    assert r.status_code == 204
    cookie = r.headers["Set-Cookie"]
    assert all(a in cookie for a in ("HttpOnly", "Secure", "SameSite=Strict"))
    with motor_bd.connect() as bd:
        hashes = bd.execute(text("SELECT hash_clave FROM sistema.usuario")).scalars().all()
    assert hashes and all(h.startswith("$argon2id$") for h in hashes)


def test_cp17_bloqueo_y_limite_de_solicitudes(motor_bd: Any) -> None:
    correo = "bloqueo@pruebas.pfc"
    with motor_bd.begin() as bd:
        bd.execute(
            text("""INSERT INTO sistema.usuario (id_rol, nombre, correo, hash_clave)
                    SELECT 3, 'Bloqueo', :c, hash_clave FROM sistema.usuario
                    WHERE correo = 'ase@pruebas.pfc'
                    ON CONFLICT (correo) DO UPDATE
                    SET intentos_fallidos = 0, bloqueado_hasta = NULL"""),
            {"c": correo},
        )
    c = Cliente()
    codigos = [c.entrar(correo=correo, contra="incorrecta").status_code for _ in range(5)]
    assert codigos == [401, 401, 401, 401, 423]
    assert c.entrar("ASESOR").status_code == 204
    # El proxy limita a 30/min con ráfaga de 10: un bucle agresivo termina en 429.
    atacante = Cliente()
    codigos = [
        atacante.s.post(
            f"{atacante.base}/auth/login", json={"correo": correo, "clave": "x"}
        ).status_code
        for _ in range(30)
    ]
    assert 429 in codigos
    time.sleep(25)


def test_cp18_indicadores_completos(clientes: dict) -> None:
    datos = clientes[ASE].get("/indicadores").json()
    assert any(m["nombre"] == "AUC_ROC" for m in datos["metricas"])
    assert {d["variable"] for d in datos["deriva"]} == {
        "anom_tsm",
        "precip_ant90_mm",
        "precip_max3d_mm",
    }
    assert sum(n["celdas_mes"] for n in datos["distribucion_niveles"]) == 34382137
    inferencia = next(p for p in datos["procesamientos"] if p["tipo"] == "INFERENCIA")
    assert inferencia["memoria_max_gb"] > 0 and "copy" in inferencia["tiempos_s"]


def test_cp19_filtros_de_bitacora(clientes: dict) -> None:
    ase = clientes[ASE]
    errores = ase.get("/bitacora", params={"tipo": "ERROR"}).json()["eventos"]
    assert errores and all(e["tipo"] == "ERROR" for e in errores)
    fechas = [e["ocurrido_en"] for e in ase.get("/bitacora").json()["eventos"]]
    assert fechas == sorted(fechas, reverse=True)
    assert ase.get("/bitacora", params={"desde": "2030-01-01"}).json()["eventos"] == []


def test_cp20_tesela_decodificada(clientes: dict) -> None:
    import mapbox_vector_tile

    r = clientes[ESP].get("/mapas/susceptibilidad/2023-03/7/36/66.pbf")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/vnd.mapbox-vector-tile"
    assert r.headers["Content-Encoding"] == "gzip"
    capa = mapbox_vector_tile.decode(r.content)["susceptibilidad"]
    assert capa["extent"] == 4096 and len(capa["features"]) > 100
    primera = capa["features"][0]
    assert {"id_celda", "nivel", "probabilidad"} <= set(primera["properties"])
    assert primera["geometry"]["type"] in ("Polygon", "MultiPolygon")
    for f in capa["features"]:
        assert f["properties"]["nivel"] in (1, 2, 3, 4)
    assert clientes[ESP].get("/mapas/susceptibilidad/2026-08/7/36/66.pbf").status_code == 404


@pytest.mark.parametrize(
    ("filtro", "columna"),
    [("departamento=24", "left(ubigeo_prov, 2)"), ("provincia=1301", "ubigeo_prov")],
)
def test_cp21_filtro_espacial_en_tesela(
    clientes: dict, motor_bd: Any, filtro: str, columna: str
) -> None:
    import mapbox_vector_tile

    valor = filtro.split("=")[1]
    zona = {"24": (7, 35, 65), "1301": (7, 36, 66)}[valor]
    z, x, y = zona
    r = clientes[ESP].get(f"/mapas/susceptibilidad/2023-03/{z}/{x}/{y}.pbf?{filtro}")
    assert r.status_code == 200, r.status_code
    celdas = {
        f["properties"]["id_celda"]
        for f in mapbox_vector_tile.decode(r.content)["susceptibilidad"]["features"]
    }
    with motor_bd.connect() as c:
        ajenas = c.execute(
            text(f"""SELECT count(*) FROM ref.celda_analisis
                     WHERE id_celda = ANY(:ids) AND {columna} <> :v"""),
            {"ids": list(celdas), "v": valor},
        ).scalar_one()
    assert celdas and ajenas == 0


def test_cabeceras_de_seguridad_en_estaticos_y_api() -> None:
    c = Cliente()
    for ruta in (f"{c.base}/salud", c.base.removesuffix("/api") + "/visor/"):
        h = c.s.get(ruta).headers
        assert "frame-ancestors 'none'" in h["Content-Security-Policy"]
        assert h["X-Frame-Options"] == "DENY" and h["X-Content-Type-Options"] == "nosniff"
        assert "max-age" in h["Strict-Transport-Security"]
        assert "nginx/" not in h.get("Server", "")


def test_inyeccion_en_parametros_se_rechaza(clientes: dict) -> None:
    esp = clientes[ESP]
    ataque = "' OR 1=1 --"
    assert (
        esp.get("/consulta-punto", params={"periodo": ataque, "lat": -7, "lon": -79}).status_code
        == 400
    )
    assert (
        esp.get(
            "/consulta-punto", params={"periodo": "2023-03", "lat": ataque, "lon": -79}
        ).status_code
        == 400
    )
    assert (
        esp.get(f"/mapas/susceptibilidad/2023-03/7/36/66.pbf?provincia={ataque}").status_code
        == 400
    )


@pytest.mark.skipif("PFC_AUDITAR_CP25" not in os.environ, reason="se ejecuta con el ciclo C1")
def test_cp25_contrato_de_capas() -> None:
    salida = subprocess.run(["lint-imports"], capture_output=True, text=True, check=False)
    assert salida.returncode == 0, salida.stdout
