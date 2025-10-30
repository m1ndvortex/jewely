"""
Forms for the reporting system.
"""

import json

from django import forms
from django.core.exceptions import ValidationError

from apps.reporting.models import Report


class ReportForm(forms.ModelForm):
    """Form for creating and editing reports."""

    output_formats = forms.MultipleChoiceField(
        choices=Report.OUTPUT_FORMATS,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        help_text="Select one or more output formats for this report",
    )

    class Meta:
        model = Report
        fields = ["name", "description", "category", "query_config", "parameters", "output_formats"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "placeholder": "e.g., Monthly Sales Summary",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white",
                    "rows": 3,
                    "placeholder": "Describe what this report does...",
                }
            ),
            "category": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                }
            ),
            "query_config": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white font-mono text-sm",
                    "rows": 12,
                    "placeholder": "Enter JSON query configuration...",
                }
            ),
            "parameters": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white font-mono text-sm",
                    "rows": 8,
                    "placeholder": "Enter parameters configuration...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make category required
        self.fields["category"].required = True
        # Make parameters optional (default dict will be used if empty)
        self.fields["parameters"].required = False

        # Only set initial values when editing existing reports
        if self.instance and self.instance.pk:
            # Convert JSON to string for display when editing
            if isinstance(self.instance.query_config, dict) and self.instance.query_config:
                self.fields["query_config"].initial = json.dumps(
                    self.instance.query_config, indent=2
                )
            if isinstance(self.instance.parameters, dict) and self.instance.parameters:
                self.fields["parameters"].initial = json.dumps(self.instance.parameters, indent=2)
            if isinstance(self.instance.output_formats, list):
                self.initial["output_formats"] = self.instance.output_formats

    def clean_query_config(self):
        """Validate and parse query_config JSON."""
        data = self.cleaned_data["query_config"]

        # If empty string, return empty dict (will be validated by model later)
        if not data or (isinstance(data, str) and data.strip() == ""):
            return {}

        # If it's already a dict, return it
        if isinstance(data, dict):
            return data

        # Try to parse as JSON string
        try:
            if isinstance(data, str):
                parsed = json.loads(data)
                return parsed
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON format in Query Configuration: {str(e)}")

        return data

    def clean_parameters(self):
        """Validate and parse parameters JSON."""
        data = self.cleaned_data["parameters"]

        # If empty, return empty dict
        if not data or data.strip() == "":
            return {}

        # If it's already a dict, return it
        if isinstance(data, dict):
            return data

        # Try to parse as JSON string
        try:
            if isinstance(data, str):
                parsed = json.loads(data)
                return parsed
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON format in Parameters: {str(e)}")

        return data

    def clean_output_formats(self):
        """Ensure output_formats is a list."""
        formats = self.cleaned_data["output_formats"]
        if isinstance(formats, str):
            return [formats]
        return list(formats)
