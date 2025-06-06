import random
import string
from django.forms import ModelForm
from django.shortcuts import render,redirect
from django.urls import reverse_lazy,reverse
from django.contrib.auth import login
from django.views.generic import CreateView
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.views import LoginView
from django.contrib.auth import authenticate, login as auth_login

from mainapps.email_system.emails import send_html_email
from mainapps.management.security.encripters import decrypt_data, management_dispatch_dispatcher

from .models_activity import CompanyProfile 
from .forms import *

StaffUser= settings.AUTH_USER_MODEL

# def login_staff(request):
#     if request.method == 'POST':
#         form = CustomLoginForm(request.POST)
#         if form.is_valid():
#             username = form.cleaned_data.get('username')
#             company_id = form.cleaned_data.get('company_id')
#             password = form.cleaned_data.get('password')
#             company=CompanyProfile.objects.get(unique_id=company_id)
#             user = authenticate(request, username=username, password=password,company_id=company_id)
#             if user is not None:
#                 # Explicitly specify the backend
#                 user.backend = 'mainapps.management.backends.StaffUserBackend'
#                 auth_login(request, user, backend='mainapps.management.backends.StaffUserBackend')
#                 return redirect(reverse('common:home'))
#                 # return redirect(reverse('accounts:send_code'))
#             else:
#                 # Invalid login
#                 form.add_error(None, "Invalid username or password")
#     else:
#         form = CustomLoginForm()
#     return render(request, 'accounts/create.html', {'form': form,'title':"Staff User Signin"})



class CompanyProfileCreateView(LoginRequiredMixin, CreateView):
    template_name = 'accounts/create.html'
    model=CompanyProfile
    success_url = reverse_lazy('common:home')
    fields='__all__'
    context_object_name='form'
    # form_class=ModelForm
    
    
    def get_context_data(self, **kwargs ) :
        context=super().get_context_data(**kwargs)
        context['title']="Company Profile"
        # context['form']=self.get_form()
        return context
    def form_valid(self,form):
        form.instance.owner=self.request.user
        return super().form_valid(form)
    def dispatch(self, request, *args, **kwargs):
        if  not request.user.is_main or request.user.is_worker:
            return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)

class StaffUserCreateView(LoginRequiredMixin, CreateView):
    form_class = StaffUserRegistrationForm
    template_name = 'accounts/create.html'
    success_url = reverse_lazy('common:home')
    context_object_name='form'
    
    def get_context_data(self, **kwargs ) :
        context=super().get_context_data(**kwargs)
        context['title']="Add new staff"
        # context['form']=self.get_form()
        return context

    def dispatch(self, request, *args, **kwargs):
        management_dispatch_dispatcher(self=self,request=request)
        if  not request.user.is_main or request.user.is_worker:
            return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.profile = self.company
        user = form.save(commit=False)
        password = self.generate_random_password()
        user.set_password(password)
        user.is_worker=True
        user.save()
        message=f'''
        A new user with the following details have been created:
        Company ID: {self.company.unique_id}
        Username: {user.username}
        password: {password}

        '''
        print(password)
        send_html_email(
            subject='New Staff User Created',
            message=message,
            to_email=[self.company.owner.email,user.email],
            html_file='management/staff_created.html'

        )
        return super().form_valid(form)

    def generate_random_password(self, length=12):
        characters = string.ascii_letters + string.digits + string.punctuation
        return ''.join(random.choice(characters) for i in range(length))


# Gv5vsM/(T8U|

def login_staff(request):
    if request.method == 'POST':
        print('step post')

        form = CustomLoginForm(request.POST)
        if form.is_valid():
            print('step form_valid')  
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            company_id = form.cleaned_data.get('company_id')
            try:
                company = get_object_or_404(CompanyProfile, unique_id=company_id)

                if company is not None:
                    print(f'Company: company')
                    try:
                        user = authenticate(request, username=username, password=password,)
                        print(user)

                        if user is not None:
                            if not user.is_main and  user.is_worker:

                                if user.profile==company:
                                    auth_login(request, user, )
                                    print('step 4 and done')

                                    return redirect(reverse('common:home'))
                                else:
                                    form.add_error(None, "Invalid company ID")

                            else:

                                form.add_error(None, "You are using the wrong authentication method! Try Root User Signin")

                        
                    except Exception as error:
                        form.add_error(None, f"{error}")


            except Exception as error:    
                form.add_error('company_id', error)    
        
    else:
        form = CustomLoginForm()
    return render(request, 'accounts/create.html', {'form': form,'title':"Staff User Signin"})

