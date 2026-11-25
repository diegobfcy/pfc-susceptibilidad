# Plan de mantenimiento y soporte

Sistema de estimación de susceptibilidad a deslizamientos por El Niño · versión 1.0.2

## 4.1 Objetivo y periodo de soporte

El sistema se creó para probar un método de estimación de deslizamientos en el norte del Perú. Muestra qué zonas de 1 km son más propensas a deslizamientos en un mes dado, pero no dice cuándo ocurrirá uno. Los datos se procesan en momentos definidos, no de forma continua, y los resultados se revisan en sesiones programadas.

El Equipo Investigador atiende dudas, corrige fallas y ayuda a recuperar el entorno desde el inicio del piloto hasta el cierre técnico del hito 3 (semana 15 del cronograma). En la semana 16 se entregan el informe, el respaldo final y el acta. Esa semana es para documentar el cierre, no para extender la atención.

La atención cubre el procesamiento, los mapas, los indicadores, las capas del visor y el historial (CU-01 a CU-05), tanto en el servidor virtual de validación (VPS) como en el equipo usado para entrenar el modelo. Una vez fijada la versión final, solo se corrigen fallas que impidan validarla. Se pide autorización y se comprueba que sea posible volver a la versión anterior, para no perder un estado que ya funcionaba. Las mejoras se anotan para un proyecto futuro.

No hay soporte después del cierre, guardia permanente, monitoreo en campo, alertas ni atención de emergencias. Tampoco se contempla integrar el sistema con CENEPRED o INDECI ni actualizar el modelo de forma automática. El piloto sirve para validar el método, no para operar un servicio institucional. La disponibilidad de los datos externos depende de sus proveedores.

Fuente: informe del proyecto, secciones 1.4.2 (alcance), 3.2 (puesta en marcha) y 3.3 (cierre), y política de respaldo y recuperación (tabla 75 y tabla de RPO/RTO).

## 4.2 Responsables

| Función | Responsable en el piloto | Deber |
| --- | --- | --- |
| Atención y operación técnica | Equipo Investigador | Recibe los reportes y prueba las soluciones porque conoce y opera el entorno de validación. También hace los respaldos. |
| Validación funcional | Especialista en Gestión de Riesgos | Confirma si puede completar la tarea y si el resultado es adecuado para la validación. Si corresponde, aprueba los límites que separan los niveles de susceptibilidad. |
| Autorización y cierre académico | Asesor del Proyecto | Acuerda con el equipo los cambios que afecten la entrega o sus plazos y revisa los pendientes del cierre. Así no se altera lo acordado sin dejar constancia. |

Antes de la primera sesión, el Equipo Investigador debe comunicar quién recibe los reportes, quién lo reemplaza si no está disponible y qué correo privado se usará. Así el Especialista y el Asesor saben a quién acudir sin depender de una mesa de ayuda institucional.

## 4.3 Canal de reporte

Si ocurre un problema durante la sesión, avise al Equipo Investigador en ese momento. Fuera de la sesión, escriba al correo privado comunicado para el piloto. El equipo registra el problema y devuelve un número de caso para que pueda hacer seguimiento. No publique contraseñas, datos privados ni capturas que los muestren.

Indique fecha y hora, rol, pantalla, qué hizo, qué esperaba y qué ocurrió. Diga si el problema le impidió seguir. Si era un procesamiento, agregue el número de ejecución, las fechas y la zona; si era un mapa, indique la capa y el mes. Incluya la versión si la conoce y una captura sin datos privados si ayuda a entender el problema. Con esos datos el equipo puede repetir los pasos y buscar la causa.

## 4.4 Severidad y SLA

La severidad indica qué tan grave es el problema. Un SLA es un acuerdo sobre el nivel de servicio, que puede fijar plazos de atención. El proyecto no tiene ese acuerdo ni una guardia permanente. Como el piloto funciona por sesiones, la tabla propone cuándo dar una primera respuesta. Esa respuesta indica qué se hará y cuándo habrá noticias; no significa que el problema ya esté resuelto.

| Severidad | Definición y ejemplo | Primera respuesta propuesta |
| --- | --- | --- |
| Crítica | La validación no puede seguir o no se puede confiar en los datos, los resultados o la seguridad de las cuentas. | En la misma sesión si se detecta allí. Fuera de la sesión, en la próxima revisión acordada. |
| Media | Una tarea falla, pero se puede seguir con otra o usar una alternativa válida. Por ejemplo, se puede cargar un archivo aceptado si falla una fuente de datos. | Antes de volver a intentar la tarea en la siguiente sesión. |
| Baja | Una duda o un detalle que no impide trabajar; por ejemplo, un texto poco claro. | En la siguiente revisión de pendientes y, como máximo, en el cierre técnico. |

Al programar la sesión se acuerda también cuándo se revisarán los avisos entre sesiones. Si el problema es crítico, el Equipo Investigador informa al Especialista y al Asesor para decidir si se puede seguir, si hay que usar un respaldo o si se cambia la fecha. Las 4 horas de recuperación del servidor son un objetivo técnico, no un plazo para responder un mensaje.

## 4.5 Procedimiento de atención

1. **Registrar el caso.** Anotar el número, la fecha, la gravedad y quién lo atenderá. Así se puede seguir el problema hasta el cierre.
2. **Buscar la causa.** Repetir los pasos en un entorno de prueba para no afectar la sesión. Comunicar el diagnóstico inicial y cuándo habrá noticias. Si falla una fuente, usar solo un archivo permitido y verificado o reprogramar el procesamiento; un resultado incompleto no debe presentarse como válido.
3. **Probar la solución.** Antes de cambiar el servidor de validación, probar tanto la corrección como la forma de deshacerla. Acordar cuándo aplicarla para no interrumpir una sesión.
4. **Confirmar y cerrar.** Comprobar que el sistema funciona y pedir a quien reportó el problema que repita la tarea. Registrar lo ocurrido, la versión y la evidencia. Si no se resuelve antes del cierre, dejar por escrito qué falta y qué alternativa existe.

## 4.6 Mantenimiento preventivo

| Tarea | Cuándo | Responsable | Por qué |
| --- | --- | --- | --- |
| Hacer una copia de la base y guardar los archivos del procesamiento (D2). | En días con cambios, antes de cada hito o cambio en la estructura de la base y apenas se aprueben los límites de susceptibilidad. | Equipo Investigador | Evita perder trabajo y conserva lo que el Especialista aprobó. |
| Revisar conexión segura, acceso, espacio libre y trabajos pendientes. | Antes de cada sesión o procesamiento, y después de instalar un cambio. | Equipo Investigador | Permite detectar fallas antes de que interrumpan una tarea. |
| Probar una copia en un entorno separado. | En los hitos de las semanas 8 y 15, según el informe. | Equipo Investigador | Confirma que la copia sirve sin poner en riesgo los datos en uso. Se anota cuánto tardó la recuperación. |
| Revisar las fuentes, los datos de referencia y la versión del modelo. | Antes del procesamiento que los usará. | Equipo Investigador | Evita generar mapas con datos incompletos o con el modelo equivocado. |

Si se pierde el servidor, la meta es recuperar el entorno en 4 horas (RTO) y no perder más de 24 horas de trabajo que pueda repetirse (RPO). Los límites aprobados se respaldan de inmediato porque no basta con volver a ejecutar el sistema para recuperar esa aprobación. Las copias externas y los archivos D2 se gestionan aparte: restaurar la base de datos no recupera esos archivos.

Véase el [manual técnico de instalación](manual_tecnico.md) para respaldo y recuperación y el [manual de mantenimiento](manual_mantenimiento.md) para pruebas y cambios de código.

## 4.7 Transferencia al término del soporte

La entrega sirve para conservar y consultar lo que se validó. No se asigna un operador permanente porque el proyecto no contempla prestar el servicio después del cierre. El acta debe indicar quién recibe y guarda los documentos y el respaldo. Si se decide seguir operando el sistema, se necesita otro acuerdo que defina quién lo administra, con qué recursos y cómo atiende los problemas.

1. **Preparar la entrega.** El Equipo Investigador reúne el código y su versión final, el inventario con las huellas para comprobar que las imágenes de instalación, el modelo y los datos siguen intactos, los manuales, los resultados de las pruebas, el respaldo y los casos pendientes. Así queda constancia de qué versión se validó y qué faltó resolver.
2. **Comprobar los manuales.** Una persona ajena a su elaboración instala el sistema en un entorno limpio y realiza una tarea siguiendo solo las instrucciones. Esta prueba permite detectar pasos que se dieron por sabidos. Si no se realiza, se anota como pendiente.
3. **Dejar constancia y cerrar los accesos.** El Equipo Investigador, el Especialista y el Asesor firman el acta de cierre. Allí se registra quién guarda el respaldo, qué pasa con el servidor y qué accesos se conservan. Los accesos autorizados se entregan en privado y los temporales que ya no hagan falta se retiran. Las contraseñas no se escriben en el acta.