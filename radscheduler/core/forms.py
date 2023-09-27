from typing import Any
from django import forms


class DateRangeForm(forms.Form):
    start = forms.DateField(required=False)
    end = forms.DateField(required=False)

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")

        if start and end and start > end:
            raise forms.ValidationError("Start date must be before end date")
