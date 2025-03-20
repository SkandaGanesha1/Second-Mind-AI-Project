from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Automatically download and install the correct ChromeDriver
chrome_driver_path = ChromeDriverManager().install()
service = Service(chrome_driver_path)

# Start the WebDriver
driver = webdriver.Chrome(service=service)
driver.get("https://www.google.com")

print("ChromeDriver is working!")
driver.quit()
