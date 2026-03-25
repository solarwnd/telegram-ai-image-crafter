from ultralytics import YOLO
import logging

# Отключаем лишние логи YOLO
logging.getLogger("ultralytics").setLevel(logging.WARNING)

class CVModel:
    def __init__(self, model_name="yolov8n.pt"):
        # При первом запуске скачает yolov8n.pt автоматически
        self.model = YOLO(model_name)
    
    def has_object(self, image_path, conf_threshold=0.25):
        """
        Проверяет, есть ли на изображении хотя бы один распознанный объект (кроме фона).
        """
        results = self.model(image_path, conf=conf_threshold, verbose=False)
        for result in results:
            if len(result.boxes) > 0:
                return True
        return False
