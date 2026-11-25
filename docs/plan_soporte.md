# Plan de mantenimiento y soporte

Sistema de estimación de susceptibilidad a deslizamientos por El Niño · versión 1.0.2

## 4.1 Objetivo y periodo de soporte

Propuesta para la entrega académica: tres meses a partir de la fecha de puesta en marcha consignada en el acta de recepción. Incluye consultas de uso, diagnóstico, correcciones, restablecimiento del servicio y mejoras menores previamente aprobadas. No cubre nuevos módulos, ampliaciones del área de estudio, disponibilidad de proveedores externos ni respuesta a emergencias. El sistema no es un servicio de alerta.

Antes de iniciar, la organización receptora debe aprobar el alcance, las fechas, los titulares y suplentes, el canal privado y los tiempos de atención. Los objetivos siguientes no son compromisos vigentes hasta esa aprobación.

## 4.2 Responsables

| Función | Responsable propuesto | Deber |
| --- | --- | --- |
| Contacto con usuarios y recepción | Administrador designado por la organización receptora | Registrar, clasificar, canalizar y confirmar el cierre. |
| Diagnóstico y corrección | Responsable técnico del equipo del proyecto durante el periodo aprobado | Reproducir, corregir, probar y entregar instrucciones de cambio o reversión. |
| Operación y despliegue | Operador de TI de la organización | Vigilar el servicio, custodiar respaldos y ejecutar cambios autorizados. |
| Autorización | Titular del área usuaria designado en el acta | Aprobar cambios de alcance, ventanas, recuperaciones y cierre de incidencias críticas. |

El acta debe identificar a los titulares y suplentes y establecer quién recibe los casos cuando el responsable principal no esté disponible.

## 4.3 Canal de reporte

Envíe el incidente a la mesa de ayuda privada o al correo institucional del contacto identificado en el acta. Para defectos reproducibles sin información confidencial se puede usar [GitHub Issues](https://github.com/diegobfcy/pfc-susceptibilidad/issues). GitHub no sustituye el canal privado. Nunca publique credenciales, cookies, registros sin depurar ni datos restringidos.

Incluya fecha, hora y zona horaria, rol, versión o entorno, pantalla, pasos, resultado esperado, mensaje observado e impacto. Para un procesamiento, agregue el identificador, periodo y ámbito; para el visor, incluya capa y mes. Adjunte evidencia anonimizada. El contacto devuelve un número de caso.

## 4.4 Severidad y SLA

Tiempos propuestos de primera respuesta desde la recepción por el canal acordado. No son plazos de resolución. Se cuentan en horario hábil propuesto, de lunes a viernes de 09:00 a 17:00, hora de Perú, salvo feriados. No se presupone guardia fuera de horario.

| Severidad | Definición y ejemplo | Primera respuesta propuesta |
| --- | --- | --- |
| Crítica | Servicio o función esencial inaccesible sin alternativa, pérdida de datos o incidente de seguridad sospechado. | 4 horas hábiles. |
| Media | Una función falla para parte de los usuarios o hay alternativa; por ejemplo, una capa no carga y las otras siguen disponibles. | 1 día hábil. |
| Baja | Consulta, mejora menor o defecto sin bloqueo; por ejemplo, un texto confuso. | 3 días hábiles. |

Para un caso crítico, el contacto informa al operador y al autorizador tan pronto como lo clasifique y fija la próxima actualización en la primera respuesta.

## 4.5 Procedimiento de atención

1. Registre número, fecha, impacto, severidad, alcance y responsable del caso.
2. Reproduzca en un entorno aislado cuando sea posible y comunique diagnóstico inicial, alternativa y fecha estimada de actualización.
3. Prepare una corrección y su reversión. Valide en pruebas o staging; obtenga aprobación antes de aplicar en el entorno de uso.
4. Verifique salud, acceso y la tarea afectada. Solicite confirmación a quien reportó el caso.
5. Registre evidencia, versión desplegada, causa, cambios preventivos y fecha de cierre. Reabra el caso si reaparece el problema.

## 4.6 Mantenimiento preventivo

| Tarea | Frecuencia propuesta | Responsable | Evidencia |
| --- | --- | --- | --- |
| Respaldar PostGIS y los artefactos D2 correspondientes | Diaria | Operador TI | Huellas y registro de copia externa. |
| Revisar salud, cola, espacio y fallos de respaldo | Diaria | Operador TI | Registro de revisión y escalamiento. |
| Restaurar una copia en un entorno aislado | Mensual y antes de cambios mayores | Operador TI y responsable técnico | Acta con tiempos, conteos y consulta de muestra. |
| Revisar dependencias, imágenes y vigencia TLS | Mensual y ante aviso crítico | Responsable técnico y operador TI | Informe y cambios probados en staging. |
| Revisar disponibilidad de fuentes y deriva del modelo | Mensual o al incorporar datos | Equipo Investigador | Registro de fuentes, versión, periodo e indicadores. |

Véase el [manual técnico de instalación](manual_tecnico.md) para respaldo y recuperación y el [manual de mantenimiento](manual_mantenimiento.md) para pruebas y cambios de código.

## 4.7 Transferencia al término del soporte

1. La organización receptora designa al operador de TI que asumirá el sistema y al responsable técnico de continuidad.
2. El equipo entrega repositorio, etiqueta o commit instalado, inventario de imágenes y datos, los tres manuales, este plan, respaldo verificable y registro de casos abiertos. Documenta también las condiciones de acceso a las fuentes de terceros.
3. Transfiera el acceso administrativo por un canal privado autorizado; rote los secretos y verifique los permisos. El acta no debe contener claves.
4. Una persona distinta de los autores ensaya la instalación en un entorno limpio, inicia sesión y ejecuta una tarea del manual de usuario. El operador entrante comprueba además la restauración aislada y registra las evidencias y los pendientes.
5. Ambas partes firman la constancia con la fecha de transferencia, los accesos verificados, los casos pendientes y quién se hará cargo de ellos.