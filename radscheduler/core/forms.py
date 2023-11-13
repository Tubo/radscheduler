from typing import Any

from django import forms
from django.forms.formsets import formset_factory

from radscheduler.core.models import Leave, Shift


class DateRangeForm(forms.Form):
    start = forms.DateField(required=True)
    end = forms.DateField(required=True)

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")

        if start and end and start > end:
            self.add_error("start", "Start date must be before end date")


class LeaveForm(forms.ModelForm):
    template_name = "leaves/form.html"

    def clean_date(self) -> str:
        date = self.cleaned_data["date"]
        if date.weekday() > 4:
            raise forms.ValidationError("No need to apply for weekend leave")
        return date

    class Meta:
        model = Leave
        fields = ["date", "type", "portion", "comment"]


class ShiftForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = ["id", "date", "type", "registrar", "extra_duty", "stat_day"]


ShiftFormSet = formset_factory(ShiftForm, extra=0)
