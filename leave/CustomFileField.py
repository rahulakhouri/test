from django.db import models
from django.db.models import FileField
from django.forms import forms
from django.template.defaultfilters import filesizeformat
from django.utils.translation import ugettext_lazy as _

class CustomFileField(FileField):
    """
    Same as FileField, but you can specify:
        * content_types - list containing allowed content_types. Example: ['application/pdf', 'image/jpeg']
        * max_upload_size - a number indicating the maximum file size allowed for upload.
            2.5MB - 2621440
            5MB - 5242880
            10MB - 10485760
            20MB - 20971520
            50MB - 5242880
            100MB 104857600
            250MB - 214958080
            500MB - 429916160
    """
    def __init__(self, *args, **kwargs):
        self.content_types = ['application/pdf']
        self.max_upload_size = 2621440

        super(CustomFileField, self).__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):
        data = super(CustomFileField, self).clean(*args, **kwargs)

        file = data.file
        content_type = file.content_type

        if content_type in self.content_types:
            if file._size > self.max_upload_size:
                raise forms.ValidationError(_('Please keep filesize under %s. Current filesize %s') % (filesizeformat(self.max_upload_size), filesizeformat(file._size)))
        else:
            raise forms.ValidationError(_('Filetype not supported.'))

        return data
