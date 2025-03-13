import os
import shutil

# Kaynak klasör
source_folder = "/Users/ayberkturk/ayb"

# Hedef klasörün temel yolu
base_target_folder = "/Users/ayberkturk/ayb"

# Kaynak klasördeki dosyaları listele
for filename in os.listdir(source_folder):
    # Sadece görseller ve json dosyalarını işleme al
    if filename.endswith(".jpg") or filename.endswith(".json"):
        # Dosya adını `_` karakterine göre böl
        parts = filename.split("_")
        
        # Görsellerde ve json dosyalarında ortak bir mantık bul
        if len(parts) >= 3:
            # Görsel dosyalar için: "elbise_product_5_image_2.jpg" -> ürün adı = "elbise", ürün numarası = "5"
            # JSON dosyaları için: "product_elbise_6.json" -> ürün adı = "elbise", ürün numarası = "6"
            if filename.endswith(".jpg"):
                product_name = parts[0]  # Örneğin "elbise"
                product_number = parts[2]  # Örneğin "5"
            elif filename.endswith(".json"):
                product_name = parts[1]  # Örneğin "elbise"
                product_number = parts[2].split(".")[0]  # Örneğin "6"

            # Ürün adı klasörünü oluştur
            product_name_folder = os.path.join(base_target_folder, product_name)
            if not os.path.exists(product_name_folder):
                os.makedirs(product_name_folder)
            
            # Ürün numarası klasörünü oluştur
            product_number_folder = os.path.join(product_name_folder, product_number)
            if not os.path.exists(product_number_folder):
                os.makedirs(product_number_folder)
            
            # Dosyanın kaynak ve hedef tam yolları
            source_file = os.path.join(source_folder, filename)
            target_file = os.path.join(product_number_folder, filename)
            
            # Dosyayı taşı
            shutil.move(source_file, target_file)
            
            # Taşınma bilgisini yazdır
            print(f"{filename} taşındı: {target_file}")