from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, RedirectView, UpdateView

from radscheduler.core.models import Registrar
from radscheduler.users.forms import RegistrarContractForm, UserProfileForm

User = get_user_model()


def _contract_form(user) -> RegistrarContractForm | None:
    registrar = Registrar.objects.filter(user=user).first()
    return RegistrarContractForm(instance=registrar) if registrar else None


class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    slug_field = "username"
    slug_url_kwarg = "username"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object == self.request.user:
            context["user_form"] = UserProfileForm(instance=self.object)
            context["contract_form"] = _contract_form(self.object)
        return context


user_detail_view = UserDetailView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = "users/user_detail.html"
    success_message = _("Information successfully updated")

    def get(self, request, *args, **kwargs):
        # Editing happens on the profile page itself.
        return redirect(request.user.get_absolute_url())

    def get_success_url(self):
        assert self.request.user.is_authenticated  # for mypy to know that the user is authenticated
        return self.request.user.get_absolute_url()

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user_form"] = context["form"]
        context["contract_form"] = _contract_form(self.request.user)
        return context


user_update_view = UserUpdateView.as_view()


@login_required
def user_contract_view(request):
    if request.method != "POST":
        # Editing happens on the profile page itself.
        return redirect(request.user.get_absolute_url())

    registrar = get_object_or_404(Registrar, user=request.user)
    form = RegistrarContractForm(request.POST, instance=registrar)
    if form.is_valid():
        form.save()
        messages.success(request, _("Contract updated"))
        return redirect(request.user.get_absolute_url())

    context = {
        "object": request.user,
        "user_form": UserProfileForm(instance=request.user),
        "contract_form": form,
    }
    return render(request, "users/user_detail.html", context)


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse("users:detail", kwargs={"username": self.request.user.username})


user_redirect_view = UserRedirectView.as_view()
