from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.core.urlresolvers import reverse
from django.templatetags.static import static
from django.conf import settings
from yandex_translate import YandexTranslateException

from .models import Correspondent, Tag, Document, Log


class MonthListFilter(admin.SimpleListFilter):

    title = "Month"

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "month"

    def lookups(self, request, model_admin):
        r = []
        for document in Document.objects.all():
            r.append((
                document.created.strftime("%Y-%m"),
                document.created.strftime("%B %Y")
            ))
        return sorted(set(r), key=lambda x: x[0], reverse=True)

    def queryset(self, request, queryset):

        if not self.value():
            return None

        year, month = self.value().split("-")
        return queryset.filter(created__year=year, created__month=month)


class CorrespondentAdmin(admin.ModelAdmin):

    list_display = ("name", "match", "matching_algorithm")
    list_filter = ("matching_algorithm",)
    list_editable = ("match", "matching_algorithm")


class TagAdmin(admin.ModelAdmin):

    list_display = ("name", "colour", "match", "matching_algorithm")
    list_filter = ("colour", "matching_algorithm")
    list_editable = ("colour", "match", "matching_algorithm")


class DocumentAdmin(admin.ModelAdmin):

    def translate_action(self, request, queryset):
        from yandex_translate import YandexTranslate
        ya = YandexTranslate(settings.PAPERLESS_YATRANSLATE_KEY)

        for doc in queryset.all():
            length = 9999
            pieces = [doc.content[i:i+length] for i in range(0, len(doc.content), length)]
            translated_pieces = []
            try:
                for piece in pieces:
                    try:
                        piece = ya.translate(piece, settings.PAPERLESS_YATRANSLATE_LANG or 'en')
                    except YandexTranslateException as ex:
                        raise ValueError('%s failed to translate: %s' % (doc.title, ex.message))
                    translated_pieces.append(''.join(piece['text']))

                doc.translation = ''.join(translated_pieces)
                doc.save(update_fields=("translation",))
                self.message_user(request, '%s successfully translated' % doc.title)
            except ValueError as doc:
                self.message_user(request, doc.args[0])
    translate_action.short_description = 'Translate'

    actions = [translate_action]

    def get_actions(self, request):
        actions = super(DocumentAdmin, self).get_actions(request)
        if not settings.PAPERLESS_YATRANSLATE_KEY:
            del actions['translate_action']
        return actions

    class Media:
        css = {
            "all": ("paperless.css",)
        }

    search_fields = ("correspondent__name", "title", "content")
    list_display = ("created", "correspondent", "title", "tags_", "document")
    list_filter = ("tags", "correspondent", MonthListFilter)
    list_per_page = 25

    def created_(self, obj):
        return obj.created.date().strftime("%Y-%m-%d")

    def tags_(self, obj):
        r = ""
        for tag in obj.tags.all():
            colour = tag.get_colour_display()
            r += self._html_tag(
                "a",
                tag.slug,
                **{
                    "class": "tag",
                    "style": "background-color: {};".format(colour),
                    "href": "{}?tags__id__exact={}".format(
                        reverse("admin:documents_document_changelist"),
                        tag.pk
                    )
                }
            )
        return r
    tags_.allow_tags = True

    def document(self, obj):
        return self._html_tag(
            "a",
            self._html_tag(
                "img",
                src=static("documents/img/{}.png".format(obj.file_type)),
                width=22,
                height=22,
                alt=obj.file_type,
                title=obj.file_name
            ),
            href=obj.download_url
        )
    document.allow_tags = True

    @staticmethod
    def _html_tag(kind, inside=None, **kwargs):

        attributes = []
        for lft, rgt in kwargs.items():
            attributes.append('{}="{}"'.format(lft, rgt))

        if inside is not None:
            return "<{kind} {attributes}>{inside}</{kind}>".format(
                kind=kind, attributes=" ".join(attributes), inside=inside)

        return "<{} {}/>".format(kind, " ".join(attributes))


class LogAdmin(admin.ModelAdmin):

    list_display = ("created", "message", "level",)
    list_filter = ("level", "created",)


admin.site.register(Correspondent, CorrespondentAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(Document, DocumentAdmin)
admin.site.register(Log, LogAdmin)


# Unless we implement multi-user, these default registrations don't make sense.
admin.site.unregister(Group)
admin.site.unregister(User)
