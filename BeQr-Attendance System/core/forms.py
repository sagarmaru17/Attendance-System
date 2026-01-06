from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, AllowedStudent
from django.contrib.auth.models import User
from .models import CustomUser

class StudentRegistrationForm(UserCreationForm):
    enrollment_number = forms.CharField(max_length=50, required=True, help_text="Your University Enrollment No.")
    roll_number = forms.CharField(max_length=20, required=True, help_text="Your Class Roll Number")
    email = forms.EmailField(required=True)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'enrollment_number', 'roll_number']
    # --- NEW VALIDATION FUNCTION ---
    def clean_enrollment_number(self):
        enrollment_no = self.cleaned_data.get('enrollment_number')

        # 1. Check if this number is in the Master List
        # If it is NOT in the AllowedStudent table, block them.
        if not AllowedStudent.objects.filter(enrollment_number=enrollment_no).exists():
            raise forms.ValidationError("Access Denied: This Enrollment Number is not registered with the University.")

        # 2. Check if this number is already taken by another user
        if CustomUser.objects.filter(enrollment_number=enrollment_no).exists():
            raise forms.ValidationError("This student account has already been created.")

        return enrollment_no

class PasswordResetVerificationForm(forms.Form):
    username = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    enrollment_number = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enrollment Number'}))

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        enrollment_number = cleaned_data.get("enrollment_number")

        # Check if a user exists with this exact combo
        if username and enrollment_number:
            try:
                user = CustomUser.objects.get(username=username, enrollment_number=enrollment_number)
                self.user_cache = user # Store user for the view to use
            except CustomUser.DoesNotExist:
                raise forms.ValidationError("Details not found. Please check your Username and Enrollment Number.")
        return cleaned_data
    

class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        # ONLY include the fields they are allowed to edit
        fields = ['username', 'first_name', 'last_name', 'email', 'roll_number']
        
    # Optional: Add Bootstrap classes for styling
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})