"""
Forms for documentation and knowledge base management.

This module provides forms for:
- Creating and editing documentation pages
- Creating and editing runbooks
- Creating admin notes
- Searching documentation

Per Requirement 34 - Knowledge Base and Documentation
"""

from django import forms
from django.utils.text import slugify

from .documentation_models import AdminNote, DocumentationPage, Runbook


class DocumentationPageForm(forms.ModelForm):
    """
    Form for creating and editing documentation pages.

    Requirement 34.2: Provide step-by-step guides for common admin tasks.
    """

    # Override tags field to accept string input
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "tag1, tag2, tag3",
            }
        ),
        help_text="Enter tags separated by commas",
    )

    class Meta:
        model = DocumentationPage
        fields = [
            "title",
            "slug",
            "content",
            "summary",
            "category",
            "tags",
            "version",
            "status",
            "parent",
            "order",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Enter documentation title",
                }
            ),
            "slug": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "url-friendly-slug (auto-generated if empty)",
                }
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono",
                    "rows": 20,
                    "placeholder": "Enter documentation content (Markdown supported)",
                }
            ),
            "summary": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "rows": 3,
                    "placeholder": "Brief summary or excerpt",
                }
            ),
            "category": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                }
            ),
            "version": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "1.0",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                }
            ),
            "parent": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                }
            ),
            "order": forms.NumberInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "0",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make slug optional - will auto-generate from title
        self.fields["slug"].required = False
        # Make parent optional
        self.fields["parent"].required = False

    def clean_tags(self):
        """Convert comma-separated tags to list."""
        tags_input = self.cleaned_data.get("tags", "")
        if isinstance(tags_input, str):
            # Split by comma and clean up whitespace
            tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()]
            return tags if tags else []  # Return empty list instead of None
        return tags_input if tags_input else []

    def clean_slug(self):
        """Auto-generate slug from title if not provided."""
        slug = self.cleaned_data.get("slug")
        if not slug:
            title = self.cleaned_data.get("title", "")
            slug = slugify(title)
        return slug


class RunbookForm(forms.ModelForm):
    """
    Form for creating and editing runbooks.

    Requirement 34.5: Provide incident response runbooks with documented procedures.
    Requirement 34.6: Provide maintenance runbooks for routine tasks.
    Requirement 34.7: Provide disaster recovery runbooks with step-by-step procedures.
    """

    # Override tags field to accept string input
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "tag1, tag2, tag3",
            }
        ),
        help_text="Enter tags separated by commas",
    )

    class Meta:
        model = Runbook
        fields = [
            "title",
            "slug",
            "description",
            "runbook_type",
            "priority",
            "prerequisites",
            "steps",
            "expected_duration",
            "rto",
            "rpo",
            "verification_steps",
            "rollback_steps",
            "tags",
            "version",
            "changelog",
            "status",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Enter runbook title",
                }
            ),
            "slug": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "url-friendly-slug (auto-generated if empty)",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "rows": 3,
                    "placeholder": "Brief description of what this runbook covers",
                }
            ),
            "runbook_type": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                }
            ),
            "priority": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                }
            ),
            "prerequisites": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "rows": 3,
                    "placeholder": "Prerequisites or requirements before executing",
                }
            ),
            "steps": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono",
                    "rows": 10,
                    "placeholder": "Enter steps as JSON array",
                }
            ),
            "verification_steps": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono",
                    "rows": 5,
                    "placeholder": "Enter verification steps as JSON array",
                }
            ),
            "rollback_steps": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono",
                    "rows": 5,
                    "placeholder": "Enter rollback steps as JSON array",
                }
            ),
            "version": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "1.0",
                }
            ),
            "changelog": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "rows": 3,
                    "placeholder": "Change history for this runbook",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make slug optional - will auto-generate from title
        self.fields["slug"].required = False

    def clean_tags(self):
        """Convert comma-separated tags to list."""
        tags_input = self.cleaned_data.get("tags", "")
        if isinstance(tags_input, str):
            # Split by comma and clean up whitespace
            tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()]
            return tags if tags else []
        return tags_input if tags_input else []

    def clean_slug(self):
        """Auto-generate slug from title if not provided."""
        slug = self.cleaned_data.get("slug")
        if not slug:
            title = self.cleaned_data.get("title", "")
            slug = slugify(title)
        return slug


class AdminNoteForm(forms.ModelForm):
    """
    Form for creating admin notes.

    Requirement 34.9: Allow admins to add notes and tips for other admins.
    """

    # Override tags field to accept string input
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "tag1, tag2, tag3",
            }
        ),
        help_text="Enter tags separated by commas",
    )

    class Meta:
        model = AdminNote
        fields = [
            "title",
            "content",
            "note_type",
            "documentation_page",
            "runbook",
            "tags",
            "is_pinned",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Enter note title",
                }
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "rows": 5,
                    "placeholder": "Enter note content",
                }
            ),
            "note_type": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                }
            ),
            "documentation_page": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                }
            ),
            "runbook": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                }
            ),
            "tags": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "tag1, tag2, tag3",
                }
            ),
            "is_pinned": forms.CheckboxInput(
                attrs={"class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make related fields optional
        self.fields["documentation_page"].required = False
        self.fields["runbook"].required = False

    def clean_tags(self):
        """Convert comma-separated tags to list."""
        tags_input = self.cleaned_data.get("tags", "")
        if isinstance(tags_input, str):
            # Split by comma and clean up whitespace
            tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()]
            return tags if tags else []
        return tags_input if tags_input else []


class DocumentationSearchForm(forms.Form):
    """
    Form for searching documentation.

    Requirement 34: Knowledge Base and Documentation - search functionality.
    """

    query = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Search documentation...",
                "type": "search",
            }
        ),
    )

    category = forms.ChoiceField(
        required=False,
        choices=[("", "All Categories")] + DocumentationPage.CATEGORY_CHOICES,
        widget=forms.Select(
            attrs={
                "class": "px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            }
        ),
    )

    status = forms.ChoiceField(
        required=False,
        choices=[("", "All Statuses")] + DocumentationPage.STATUS_CHOICES,
        widget=forms.Select(
            attrs={
                "class": "px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            }
        ),
    )


class RunbookSearchForm(forms.Form):
    """
    Form for searching runbooks.

    Requirement 34: Knowledge Base and Documentation - search functionality.
    """

    query = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Search runbooks...",
                "type": "search",
            }
        ),
    )

    runbook_type = forms.ChoiceField(
        required=False,
        choices=[("", "All Types")] + Runbook.RUNBOOK_TYPE_CHOICES,
        widget=forms.Select(
            attrs={
                "class": "px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            }
        ),
    )

    priority = forms.ChoiceField(
        required=False,
        choices=[("", "All Priorities")] + Runbook.PRIORITY_CHOICES,
        widget=forms.Select(
            attrs={
                "class": "px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            }
        ),
    )

    status = forms.ChoiceField(
        required=False,
        choices=[("", "All Statuses")] + Runbook.STATUS_CHOICES,
        widget=forms.Select(
            attrs={
                "class": "px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            }
        ),
    )
