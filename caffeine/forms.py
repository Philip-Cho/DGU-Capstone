from django import forms
from django.contrib.auth.forms import UserCreationForm
from caffeine.models import Users

# 커스터마이징 한 UserCreationForm
class RegisterForm(UserCreationForm):
    id = forms.CharField(max_length=20, label='ID')
    username = forms.CharField(max_length=20, label='이름')
    email = forms.EmailField(max_length=40, label='e-mail')
    
    class Meta:
        model = Users
        fields = {
            'username',
            'id',
            'email',
            'password1',
            'password2',
        }