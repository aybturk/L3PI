import os
import json
import base64
import requests

class eBayProductUploader:
    def __init__(self, ebay_token, folder_path):
        self.ebay_token = ebay_token
        self.folder_path = folder_path
        self.api_url = "https://api.ebay.com/ws/api.dll"

    def get_product_data(self):
        """
        Aynı klasördeki 'product.json' dosyasını okuyup 
        ürün bilgilerini sözlük (dict) olarak döndürür.
        """
        product_json_path = os.path.join(self.folder_path, "product.json")
        with open(product_json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_images_from_folder(self):
        """
        Klasördeki .jpg, .jpeg, .png uzantılı dosyaları bulup
        tam yol listesini döndürür.
        """
        image_extensions = (".jpg", ".jpeg", ".png")
        images = [
            os.path.join(self.folder_path, f)
            for f in os.listdir(self.folder_path)
            if f.lower().endswith(image_extensions)
        ]
        print("Bulunan resim dosyaları:", images)  # Debug
        return images

    def upload_image_to_ebay(self, image_path):
        """
        Bir resmi eBay'e yükler. Resim verisini base64 ile kodlayıp
        XML içine ekler ve dönen XML yanıt içinden
        PictureURL değerini bulup döndürür.
        """
        headers = {
            "X-EBAY-API-CALL-NAME": "UploadSiteHostedPictures",
            "X-EBAY-API-SITEID": "0",
            "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
            "X-EBAY-API-IAF-TOKEN": self.ebay_token,
            "Content-Type": "text/xml"
        }

        with open(image_path, "rb") as image_file:
            image_data = image_file.read()

        # Base64 ile kodlayalım
        image_data_b64 = base64.b64encode(image_data).decode('utf-8')

        xml_payload = f"""
        <?xml version="1.0" encoding="utf-8"?>
        <UploadSiteHostedPicturesRequest xmlns="urn:ebay:apis:eBLBaseComponents">
            <Version>967</Version>
            <PictureData>{image_data_b64}</PictureData>
        </UploadSiteHostedPicturesRequest>
        """

        response = requests.post(self.api_url, headers=headers, data=xml_payload)
        if response.status_code == 200:
            text = response.text
            start_tag = "<FullURL>"
            end_tag = "</FullURL>"
            start_index = text.find(start_tag)
            end_index = text.find(end_tag)
            if start_index != -1 and end_index != -1:
                url = text[start_index + len(start_tag):end_index].strip()
                print(f"{os.path.basename(image_path)} yüklendi, URL: {url}")  # Debug
                return url
            else:
                print(f"{os.path.basename(image_path)} yüklenemedi, yanıt: {text}")
        else:
            print(f"Resim yükleme hatası {image_path}: {response.status_code}")
        return None

    def upload_all_images(self):
        """
        Klasördeki tüm resimleri eBay'e yükler ve 
        elde edilen URL listesini döndürür.
        """
        image_paths = self.get_images_from_folder()
        uploaded_urls = []
        for img in image_paths:
            url = self.upload_image_to_ebay(img)
            if url:
                uploaded_urls.append(url)
        print("Toplam yüklenen resim URL'leri:", uploaded_urls)  # Debug
        return uploaded_urls

    def build_shipping_details_xml(self, shipping_details):
        """
        JSON'daki ShippingDetails verisini XML formatına dönüştürür.
        Ek olarak ShippingServiceAdditionalCost alanını ekler.
        """
        shipping_type = shipping_details.get("ShippingType", "Flat")
        shipping_service_options = shipping_details.get("ShippingServiceOptions", [])

        shipping_service_xml = ""
        for option in shipping_service_options:
            service = option.get("ShippingService", "UPSNextDayAir")
            cost = option.get("ShippingServiceCost", "0.00")
            additional_cost = option.get("ShippingServiceAdditionalCost", cost)
            shipping_service_xml += f"""
            <ShippingServiceOptions>
                <ShippingService>{service}</ShippingService>
                <ShippingServiceCost>{cost}</ShippingServiceCost>
                <ShippingServiceAdditionalCost>{additional_cost}</ShippingServiceAdditionalCost>
            </ShippingServiceOptions>
            """

        shipping_details_xml = f"""
        <ShippingDetails>
            <ShippingType>{shipping_type}</ShippingType>
            {shipping_service_xml}
        </ShippingDetails>
        """
        return shipping_details_xml

    def build_item_specifics_xml(self, item_specifics):
        """
        JSON'daki ItemSpecifics verisini XML formatına dönüştürür.
        Her bir item specific için <NameValueList> oluşturur.
        """
        specifics_xml = "<ItemSpecifics>"
        for key, value in item_specifics.items():
            specifics_xml += f"""
            <NameValueList>
                <Name>{key}</Name>
                <Value>{value}</Value>
            </NameValueList>
            """
        specifics_xml += "</ItemSpecifics>"
        return specifics_xml

    def list_product_on_ebay(self):
        """
        JSON'daki ürün bilgilerini ve klasördeki resimleri alarak
        eBay'de ürünü listelemeye çalışır.
        """
        product_data = self.get_product_data()
        image_urls = self.upload_all_images()

        # JSON'dan ürün bilgilerini okuyalım
        title = product_data.get("Title", "Test Ürünü")
        description = product_data.get("Description", "Açıklama girilmedi.")
        category_id = product_data.get("CategoryID", "63863")
        start_price = product_data.get("StartPrice", "9.99")
        currency = product_data.get("Currency", "USD")
        condition_id = product_data.get("ConditionID", "1000")
        dispatch_time = product_data.get("DispatchTimeMax", "3")
        listing_duration = product_data.get("ListingDuration", "GTC")
        quantity = product_data.get("Quantity", "1")

        # Ülke, konum, posta kodu
        country = product_data.get("Country", "ES")
        location = product_data.get("Location", "Madrid")
        postal_code = product_data.get("PostalCode", "28001")

        # Shipping ve ItemSpecifics bilgileri
        shipping_details = product_data.get("ShippingDetails", {})
        shipping_details_xml = self.build_shipping_details_xml(shipping_details)
        item_specifics = product_data.get("ItemSpecifics", {})
        item_specifics_xml = self.build_item_specifics_xml(item_specifics)

        # PictureURL etiketlerini oluştur
        picture_details_xml = "".join(f"<PictureURL>{url}</PictureURL>" for url in image_urls)

        # Nihai XML payload
        xml_payload = f"""
        <?xml version="1.0" encoding="utf-8"?>
        <AddFixedPriceItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
            <RequesterCredentials>
                <eBayAuthToken>{self.ebay_token}</eBayAuthToken>
            </RequesterCredentials>
            <Item>
                <Title>{title}</Title>
                <Description>{description}</Description>
                <PrimaryCategory>
                    <CategoryID>{category_id}</CategoryID>
                </PrimaryCategory>
                <StartPrice>{start_price}</StartPrice>
                <Currency>{currency}</Currency>
                <ConditionID>{condition_id}</ConditionID>
                <DispatchTimeMax>{dispatch_time}</DispatchTimeMax>
                <ListingDuration>{listing_duration}</ListingDuration>
                <Quantity>{quantity}</Quantity>

                <!-- Ülke, Konum ve Posta Kodu -->
                <Country>{country}</Country>
                <Location>{location}</Location>
                <PostalCode>{postal_code}</PostalCode>

                <PictureDetails>
                    {picture_details_xml}
                </PictureDetails>

                {shipping_details_xml}
                {item_specifics_xml}
            </Item>
        </AddFixedPriceItemRequest>
        """

        headers = {
            "X-EBAY-API-CALL-NAME": "AddFixedPriceItem",
            "X-EBAY-API-SITEID": "0",
            "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
            "X-EBAY-API-IAF-TOKEN": self.ebay_token,
            "Content-Type": "text/xml"
        }

        response = requests.post(self.api_url, headers=headers, data=xml_payload)

        print("Ürün yükleme yanıtı:")
        print(response.text)

        if response.status_code == 200:
            if "<Ack>Success</Ack>" in response.text:
                print("✅ Ürün başarıyla eBay'e yüklendi!")
            else:
                print("⚠️ Ürün yüklenirken uyarı/hata olabilir, yanıtı inceleyin.")
        else:
            print(f"❌ Hata oluştu: {response.status_code}")

if __name__ == "__main__":
    # eBay User Token (örn. v^1.1#i^1#r^1#f^0#I^3#p^3#t^Ul4...)
    ebay_token = "v^1.1#i^1#r^1#f^0#I^3#p^3#t^Ul4xMF85OjM0MUE4MDIwMTU1ODUzRkFENzFCMDJBN0JFRDQwRjE5XzFfMSNFXjI2MA=="

    # Ürün görsellerinin ve product.json dosyasının bulunduğu klasör
    folder_path = "/Users/ayberkturk/ayb/Trendyol_Products/Kadın/Mavi ceket"

    uploader = eBayProductUploader(ebay_token, folder_path)
    uploader.list_product_on_ebay()