from typing import Any

from django import forms

from radscheduler.core.models import Leave


class DateRangeForm(forms.Form):
    start = forms.DateField(required=False)
    end = forms.DateField(required=False)

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")

        if start and end and start > end:
            raise forms.ValidationError("Start date must be before end date")


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
