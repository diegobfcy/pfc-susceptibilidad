# Plan de mantenimiento y soporte

Sistema de estimación de susceptibilidad a deslizamientos por El Niño · versión 1.0.2

## 4.1 Objetivo y periodo de soporte

El sistema es una prueba de concepto académica: estima susceptibilidad mensual en celdas de 1 km en el norte del Perú, se ejecuta por lotes y se usa en sesiones programadas. El soporte del Equipo Investigador abarca desde la puesta en marcha del piloto hasta el cierre técnico del hito 3 (semana 15 según el cronograma). El informe, el respaldo final y el acta se entregan en la semana 16; esa entrega no amplía el periodo de soporte.

Se atienden consultas, incidencias y correcciones que permitan validar los casos CU-01 a CU-05: procesamiento, mapas, indicadores, capas e historial. El alcance comprende el VPS de validación y la estación de entrenamiento. Durante la congelación del código solo se consideran correcciones necesarias para la validación, con autorización y prueba de reversión; las mejoras se registran como trabajo futuro.

Quedan fuera el soporte posterior al cierre, la producción institucional, la operación 24/7, el monitoreo en campo, la emisión de alertas, la respuesta a emergencias, la integración con CENEPRED o INDECI, y la actualización autónoma del modelo. Tampoco se garantiza la disponibilidad de las fuentes externas.

Base del plan: informe del proyecto, §1.4.2 (alcance y exclusiones), política de respaldo y restauración (tabla 75 y tabla de RPO/RTO), §3.2 (implantación formal) y §3.3 (cierre).

## 4.2 Responsables

| Función | Responsable en el piloto | Deber |
| --- | --- | --- |
| Atención y operación técnica | Equipo Investigador | Recibir y registrar casos, diagnosticar, respaldar, restaurar y aplicar cambios autorizados en validación. |
| Validación funcional | Especialista en Gestión de Riesgos | Comunicar el impacto en las sesiones, validar la función afectada y aprobar los umbrales cuando corresponda. |
| Autorización y cierre académico | Asesor del Proyecto | Acordar con el equipo los cambios que afecten la entrega o sus hitos y revisar pendientes y evidencias de cierre. |

Antes de las sesiones, el Equipo Investigador confirma el contacto principal, su respaldo dentro del equipo y el canal privado con el Especialista y el Asesor. No se presupone una mesa de ayuda ni un operador institucional permanente.

## 4.3 Canal de reporte

Durante una sesión, comunique el incidente al Equipo Investigador para que lo registre. Fuera de la sesión, use el correo privado acordado para el piloto. La bitácora de incidencias es el registro de atención; publicar un defecto no abre un compromiso de soporte. No comparta credenciales, cookies, registros sin depurar ni datos restringidos.

Incluya fecha, hora y zona horaria, rol, versión o entorno, pantalla, pasos, resultado esperado, mensaje observado e impacto. Para un procesamiento, agregue el identificador, periodo y ámbito; para el visor, incluya capa y mes. Adjunte evidencia anonimizada. El contacto devuelve un número de caso.

## 4.4 Severidad y SLA

El informe no establece un SLA contractual ni una guardia. Los siguientes objetivos de primera respuesta sirven para coordinar el piloto y se confirman al programar cada sesión; no son plazos garantizados de resolución.

| Severidad | Definición y ejemplo | Primera respuesta propuesta |
| --- | --- | --- |
| Crítica | No se puede continuar una sesión o cumplir un hito; se sospecha pérdida de datos, resultados inválidos o exposición de credenciales. | Durante la sesión si se detecta allí; fuera de sesión, en la siguiente revisión acordada con el equipo. |
| Media | Una tarea falla pero puede ejecutarse otra, o hay una alternativa válida; por ejemplo, carga manual cuando falla una fuente y se dispone del archivo admitido. | Antes de repetir la tarea afectada en la siguiente sesión acordada. |
| Baja | Consulta o defecto que no bloquea la validación. | En la siguiente revisión de pendientes, a más tardar durante el cierre técnico. |

Para una incidencia crítica, el Equipo Investigador informa al Especialista y al Asesor y acuerda si se continúa, se restaura o se reprograma. El RTO de 4 h es un objetivo de recuperación ante la pérdida del VPS, no un SLA de atención.

## 4.5 Procedimiento de atención

1. Registre número, fecha, impacto, severidad, alcance y responsable del caso.
2. Distinga un fallo de acceso, procesamiento, fuente externa o consulta de resultados. Registre el identificador del trabajo, el periodo y la versión del modelo cuando apliquen. No presente como válido un resultado incompleto o dudoso.
3. Reproduzca el fallo en un entorno aislado y comunique el diagnóstico inicial y la próxima actualización. Si falla una fuente, use solo una carga manual admitida y verificada o reprograme la corrida.
4. Si requiere cambio, prepare la corrección y su reversión, pruébelas y acuerde la intervención antes de aplicarla en el VPS de validación. Compruebe salud, acceso y la tarea afectada con el rol correspondiente.
5. Registre evidencia, causa, versión y conformidad. Cierre el caso o deje documentados su impacto, alternativa y estado al cierre del piloto.

## 4.6 Mantenimiento preventivo

| Tarea | Momento previsto | Responsable | Evidencia |
| --- | --- | --- | --- |
| Respaldar la base y preservar los artefactos D2 necesarios para reproducir la corrida | En días con cambios; antes de cada hito o cambio de esquema, e inmediatamente al aprobar umbrales | Equipo Investigador | Huellas SHA-256, versión y ubicación de copias. |
| Comprobar HTTPS, salud, cola, espacio y acceso por rol | Antes de cada sesión o lote y después de desplegar | Equipo Investigador | Prueba de humo y resultado registrado. |
| Ensayar una restauración aislada | Hitos de las semanas 8 y 15, según el informe | Equipo Investigador | Tiempo, conteos, integridad y consulta de muestra. |
| Verificar las fuentes, datos de referencia y artefacto del modelo | Antes de la corrida que los utiliza | Equipo Investigador | Fuente, periodo, versión, huella y resultado de validación. |

La política del informe prevé un RPO de hasta 24 h para trabajo reproducible y un respaldo inmediato de umbrales aprobados. Las copias externas y la custodia de D2 se gestionan según esa política; no se presume que los scripts de base de datos automaticen por sí solos esa replicación ni la recuperación de D2.

Véase el [manual técnico de instalación](manual_tecnico.md) para respaldo y recuperación y el [manual de mantenimiento](manual_mantenimiento.md) para pruebas y cambios de código.

## 4.7 Entrega y cierre del piloto

1. El Equipo Investigador prepara el repositorio y la versión final, el inventario y las huellas de imágenes, modelo y datos, los manuales, las evidencias de validación, el respaldo final verificable y los casos abiertos.
2. Como verificación documental, una persona distinta de los autores ensaya la instalación en un entorno limpio y ejecuta una tarea del manual de usuario. Registre la evidencia o deje explícito que la verificación no se realizó; no equivale a aceptar una operación institucional.
3. Registre en el acta la conformidad funcional, los pendientes, la custodia del respaldo y la decisión sobre accesos y el VPS. Entregue por un canal privado solo los accesos autorizados y revoque los temporales que ya no se necesiten. No incluya claves en el acta.
4. Formalice la entrega con el Acta de Conformidad y Cierre del Proyecto, para firma del Equipo Investigador, el Especialista y el Asesor. Cualquier continuidad posterior requiere un acuerdo separado que defina propietario, recursos, canales y compromisos; no se transfiere una obligación de operación o atención con esta entrega.