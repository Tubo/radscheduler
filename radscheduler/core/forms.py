from collections.abc import Mapping
from datetime import date
from typing import Any

from crispy_forms.bootstrap import InlineCheckboxes
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Field, Layout, Submit
from django import forms
from django.core.files.base import File
from django.db.models.base import Model
from django.forms.formsets import formset_factory
from django.forms.utils import ErrorList

from radscheduler.core.models import Leave, Registrar, Shift, ShiftInterest
from radscheduler.core.service import get_active_registrars
from radscheduler.roster import canterbury_holidays
from radscheduler.roster.models import LeaveType, ShiftType


class DateForm(forms.Form):
    date = forms.DateField()


class EventsFilterForm(forms.Form):
    shift_types = forms.MultipleChoiceField(
        choices=ShiftType.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        initial=ShiftType.values,
    )
    leave_types = forms.MultipleChoiceField(
        choices=LeaveType.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        initial=LeaveType.values,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True

        self.helper.layout = Layout(
            Div(
                # auto-submit form when checkbox is clicked with unpoly
                Div(InlineCheckboxes("shift_types", up_autosubmit="")),
                Div(InlineCheckboxes("leave_types", up_autosubmit="")),
                css_class="row row-cols-auto justify-content-start",
            )
        )


class DateTimeRangeForm(forms.Form):
    start = forms.DateTimeField(required=True)
    end = forms.DateTimeField(required=True)

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")

        if start and end and start > end:
            self.add_error("start", "Start date must be before end date")


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
    registrar = forms.IntegerField(widget=forms.HiddenInput(), required=False)

    def clean_date(self) -> str:
        leave_date = self.cleaned_data["date"]
        if leave_date < date.today():
            raise forms.ValidationError("Unable to apply for leave in the past")
        if leave_date.weekday() > 4:
            raise forms.ValidationError(f"{leave_date.strftime('%d/%m/%Y')} is a weekend")
        return leave_date

    def clean_registrar(self) -> Registrar:
        if self.instance.registrar_id:
            return self.instance.registrar
        registrar_id = self.cleaned_data["registrar"]
        return Registrar.objects.get(id=registrar_id) if registrar_id else None

    class Meta:
        model = Leave
        fields = ["date", "type", "portion", "comment", "registrar"]


class ShiftChangeForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = ["registrar"]


class ShiftAddForm(forms.ModelForm):
    registrar = forms.ModelChoiceField(queryset=get_active_registrars(), required=False)

    class Meta:
        model = Shift
        fields = ["date", "type", "registrar", "stat_day", "extra_duty"]


class ShiftInterestForm(forms.ModelForm):
    class Meta:
        model = ShiftInterest
        fields = ["comment"]
