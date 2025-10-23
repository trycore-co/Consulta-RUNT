from app.services.notification_service import NotificationService

notif = NotificationService()
print("✅ Probando envío de correos...")
# --- Inicio ---
notif.send_start_notification(5)
# --- Error controlado ---
notif.send_failure_controlled(
    record_id="123",
    motivo="Documento no registrado en el sistema RUNT.",
    input_masked="CC-1032****",
)
# --- Error inesperado ---
notif.send_failure_unexpected(
    record_id="456",
    error="Timeout al intentar cargar la página del detalle de vehículo.",
    last_screenshot="data/capturas/detalle_RAK384.png",  # opcional
)
# --- Fin ---
notif.send_end_notification(
    exitosos=4,
    errores=1,
    pdf_path="data/pdfs/Kick Off - RPA - CISA - Consulta RUNT.pdf",
)

print("📨 Correos enviados exitosamente (verifica tu bandeja).")
