# users/serializers.py

from rest_framework import serializers
from .models import PDFBookmark, PDFAnnotation

class PDFBookmarkSerializer(serializers.ModelSerializer):
    """Сериализатор для модели закладок PDF"""
    class Meta:
        model = PDFBookmark
        fields = ['id', 'user', 'material', 'page_number', 'comment', 'created_at']
        read_only_fields = ['user', 'created_at']  # Эти поля заполняются автоматически

    def create(self, validated_data):
        """Автоматически привязываем закладку к текущему пользователю"""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class PDFAnnotationSerializer(serializers.ModelSerializer):
    """Сериализатор для модели аннотаций PDF"""
    class Meta:
        model = PDFAnnotation
        fields = ['id', 'user', 'material', 'page_number', 'annotation_type', 
                  'content', 'created_at', 'updated_at']
        read_only_fields = ['user', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Автоматически привязываем аннотацию к текущему пользователю"""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)