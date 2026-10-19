"""
Keep uploaded document files in step with their records: a file that is
replaced, removed or whose document is deleted is removed from storage once
the transaction commits (so a rolled-back change never loses a file).
"""
from django.db import transaction
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import Document


def _delete_later(storage, name):
    if name:
        transaction.on_commit(lambda: storage.delete(name))


@receiver(pre_save, sender=Document)
def delete_replaced_file(sender, instance, raw=False, **kwargs):
    if raw or instance._state.adding:
        return
    old = sender.objects.filter(pk=instance.pk).values_list("file", flat=True).first()
    if old and old != instance.file.name:
        _delete_later(instance.file.storage, old)


@receiver(post_delete, sender=Document)
def delete_file_with_document(sender, instance, **kwargs):
    _delete_later(instance.file.storage, instance.file.name)
