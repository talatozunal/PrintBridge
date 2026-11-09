# -*- coding: utf-8 -*-
"""Protokolde tanımlı hata kodları (docs/PROTOCOL.md §3)."""

from __future__ import annotations


class AppError(Exception):
    """HTTP katmanına taşınacak, kullanıcıya gösterilebilir hata."""

    http_status = 500
    code = "internal_error"
    message = "Beklenmeyen bir hata oluştu."

    def __init__(self, message: str | None = None, *, detail: str | None = None, code: str | None = None):
        super().__init__(message or self.message)
        if message:
            self.message = message
        if code:
            self.code = code
        self.detail = detail


class Unauthorized(AppError):
    http_status = 401
    code = "unauthorized"
    message = "Geçersiz veya süresi dolmuş eşleştirme anahtarı."


class InvalidPin(AppError):
    http_status = 401
    code = "invalid_pin"
    message = "PIN hatalı veya süresi doldu."


class TooManyAttempts(AppError):
    http_status = 429
    code = "too_many_attempts"
    message = "Çok fazla yanlış PIN denemesi. PC'de yeni PIN oluşturun."


class UnsupportedType(AppError):
    http_status = 400
    code = "unsupported_type"
    message = "Bu dosya türü desteklenmiyor. JPEG, PNG, HEIC, PDF veya TXT gönderin."


class TooLarge(AppError):
    http_status = 413
    code = "too_large"
    message = "Dosya boyut sınırını aşıyor."


class InvalidOptions(AppError):
    http_status = 422
    code = "invalid_options"
    message = "Yazdırma seçenekleri geçersiz."


class PrinterUnavailable(AppError):
    http_status = 409
    code = "printer_offline"
    message = "Yazıcı hazır değil. USB kablosunu ve gücü kontrol edin."


class RenderFailed(AppError):
    http_status = 422
    code = "render_failed"
    message = "Dosya yazdırmaya hazırlanamadı (bozuk veya desteklenmeyen içerik)."


class SpoolFailed(AppError):
    http_status = 500
    code = "spool_failed"
    message = "Windows yazdırma kuyruğuna gönderilemedi."


class Busy(AppError):
    http_status = 423
    code = "busy"
    message = "Yazdırma kuyruğu dolu, biraz sonra tekrar deneyin."


class NotFound(AppError):
    http_status = 404
    code = "not_found"
    message = "İş bulunamadı."


class Conflict(AppError):
    http_status = 409
    code = "conflict"
    message = "İş bu durumda değiştirilemez."


class JobCanceled(Exception):
    """Worker içinde iptal sinyali; HTTP'ye çıkmaz."""
