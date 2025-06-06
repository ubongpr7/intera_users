from django.shortcuts import get_object_or_404, redirect, render
from django.core.mail import send_mail
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate,logout
from django.views import generic
from django.contrib import messages
from django.conf import settings
from django.urls import reverse

from .forms import CustomUserCreationForm, CustomLoginForm
from django.contrib.auth import authenticate, login as auth_login


from mainapps.email_system.emails import send_html_email


from .models import User,VerificationCode
 







class LandingPage(generic.TemplateView):
    template_name='accounts/landing_page.html'

class LoginPage(generic.TemplateView):
    template_name='accounts/login.html'

class RegisterPage(generic.TemplateView):
    template_name='accounts/register.html'




def register_owner(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():

            user = form.save()
            user.is_main=True
            user.save()
            
            messages.success(request, 'Account created successfully. We have sent a verification code to your email. Use it to verify but do not expose it to anyone!')
            request.session['pk']=user.pk
            request.session["verified "]=False
            print(request.session['pk'])
            return redirect(reverse('account:verification')) 
            # return redirect(reverse('common:home'))
            # return redirect(reverse('accounts:send_code'))
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/create.html', {'form': form,'title':'Root User Registration'})

def login_owner(request):
    if request.method == 'POST':
        form = CustomLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                # Explicitly specify the backend
                if user.is_main: 
                    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    next_url= request.GET.get('next')
                    if next_url:
                        return redirect(next_url)
                    else:    
                        return redirect(reverse('common:home'))
                else:
                    form.add_error(None, "Wrong authentication method! Try Staff Login ")

                # return redirect(reverse('accounts:send_code'))
            else:
                # Invalid login
                form.add_error(None, "Invalid username or password")
    else:
        form = CustomLoginForm()
    return render(request, 'accounts/create.html', {'form': form,'title':"Root User Signin"})


def get_verification(request):
    pass 

def index(request):
  return render(request, 'index.html')
  
def signout(request):
    logout(request)
    messages.success(request,'Logout Successful')
    return redirect('/')
    
def signin(request):
    title='Signin'

    if request.method == 'POST':
        username = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(username=username, password=password)

        if user is not None:
            
            messages.success(request, 'We have sent a verification code to your email.')
            request.session['pk']=user.pk
            request.session["verified "]=False

            return redirect('/accounts/verification') 
        else:
            messages.error(request, 'Invalid username or password.')
            return render(request ,'accounts/login.html')
    return render(request, 'accounts/login.html',{'title':title})
        
def send_code(request):
    pk =request.session.get('pk')
    verified=request.session.get("verified ")

    if pk:
        user= User.objects.get(pk=pk)
        code =VerificationCode.objects.get(slug=user.username)
        code.total_attempts+=1
        code.save()
        code =VerificationCode.objects.get(slug=user.username)
        print(code)
        messages.success(request,'Code sent')
        return redirect('/verification')
    else:
        messages.error(request,'Session expired')
        return redirect('/signin')
    return redirect('/account/verification')



def twofa(request):
    title="Authentications"
    pk=request.session.get('pk')
    verified=request.session.get("verified ")

    if verified:  
        return redirect("/")
    else:
        if pk:
            print(f'pk: {pk}')
            user =User.objects.get(pk=pk)
            html_file='accounts/verify.html'
            to_email=user.email
            code=VerificationCode.objects.get(slug=user.email)
            code.total_attempts+=1
            code.save()
            code =VerificationCode.objects.get(slug=user.username)
            
            print(f'this is the code: {code}')
            subject=f'Verification code: {code}. {user.first_name} {user.last_name}'
            message= code
            
            
            if request.method!="POST":
            
                
                send_html_email(subject, message,  [to_email],html_file)
            if request.method=="POST":
                
                num=request.POST.get('code')
                print(num)
                
                if str(code)==num:
                    code.successful_attempts+=1
                    code.save()
                    login(request, user)
                    messages.success(request,"Authentication Successful!")
                    request.session["verified "]=True
                    
                    return redirect('/')
                else :
                    messages.error(request,"You have entered an invalid code and therefore need to restart Authentication for security reasons")
                    return redirect('/accounts/signin')
    return render(request,"accounts/twofa.html",{'title':title})
def get_verification(request):
    pass 

def register(request):
    title="Registration"
    if request.method == 'POST':
        username = request.POST.get('email1')
        email = request.POST.get('email2')
        first_name=request.POST.get('first_name') 
        last_name=request.POST.get('last_name') 
        password = request.POST.get('password1')
        confirm_password = request.POST.get('confirm_password')
        if not (username and email and password and confirm_password):
            messages.error(request, 'All fields are required.')
            return render(request, 'authentication-register.html')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'authentication-register.html')


        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
            return render(request, 'authentication-register.html')

        user = User.objects.create_user(username=username,first_name=first_name,last_name=last_name, email=email, password=password)

        user = authenticate(username=username, password=password)
        
        messages.success(request, 'Account created successfully. We have sent a verification code to your email. Use it to verify but do not expose it to anyone!')
        request.session['pk']=user.pk
        request.session["verified "]=False

        return redirect('/account/verification')  

    return render(request, 'authentication-register.html',{'title':title})
