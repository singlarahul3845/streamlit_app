import streamlit as st
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
from io import BytesIO
import pyperclip  # Import pyperclip for clipboard operations

# Function to scrape content from a URL
def scrape_blog_content(url):
    try:
        # Send a GET request to fetch the content of the page
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        
        # Check for a successful response
        if response.status_code != 200:
            return "Failed to retrieve content."
        
        # Parse the HTML content of the page
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the main content within the 'post-content' div
        post_content = soup.find("div", class_="post-content")
        
        # If no content found, return an error
        if not post_content:
            return "Content not found."
        
        # Decompose the unwanted elements

        # Remove images
        for img in post_content.find_all("img"):
            img.decompose()

        # Remove anchor tags with .html endings
        for a in post_content.find_all("a"):
            if "href" in a.attrs and a["href"].endswith(".html"):
                a.decompose()

        # Remove all headings (h1 to h6)
        for heading in post_content.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            heading.decompose()

        # Remove divs with specific excluded classes
        exclude_classes = ["yarpp", "yarpp-related", "yarpp-related-website", 
                           "yarpp-template-list", "wordpress-search1", "wordpress-term1"]
        for div in post_content.find_all("div", class_=lambda x: x and any(cls in x for cls in exclude_classes)):
            div.decompose()

        # Now, we only keep the content inside <p>, <ol>, <ul>, and <li> tags, preserving the structure
        paragraphs = post_content.find_all(['p', 'ol', 'ul'])

        # Initialize an empty string to store the content
        content = ''

        # Process each element (p, ol, ul, li)
        for elem in paragraphs:
            if elem.name == 'p':  # Paragraphs
                content += handle_inline_tags(elem) + '\n\n'
            elif elem.name in ['ol', 'ul']:  # Lists
                content += '\n' + handle_list_items(elem)  # Process list items directly here

        return content.strip()  # Remove the last newline for clean output

    except Exception as e:
        return f"Error: {str(e)}"

# Helper function to handle inline tags like <strong>, <em>, etc., and add space between elements
def handle_inline_tags(elem):
    text = ''
    
    # Iterate through the elements inside <p>, <ul>, <ol>, or <li>
    for child in elem.children:
        if isinstance(child, str):  # If the child is a text node
            text += child
        elif child.name in ['strong', 'em', 'a']:  # Inline tags like <strong>, <em>, etc.
            text += child.get_text(strip=True)
        
        # Add space after inline tags
        if child.name in ['strong', 'em', 'a']:
            text += ' '
    
    return text.strip()  # Return the cleaned text

# Helper function to handle list items <li> inside <ol> and <ul>
def handle_list_items(elem):
    list_content = ''
    for li in elem.find_all('li'):
        list_content += handle_inline_tags(li) + '\n'
    return list_content

# Function to detect AI content using Selenium and Quillbot
def detect_ai_content(content):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")  # Required for headless operation
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Automatically install and use ChromeDriver
    driver = webdriver.Chrome(service=webdriver.chrome.service.Service(ChromeDriverManager().install()), options=chrome_options)
    
    driver.get("https://quillbot.com/ai-content-detector")
    time.sleep(5)
    
    try:
        input_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "aidr-input-editor"))
        )
        input_box.click()
        time.sleep(1)
        
        # Copy content to clipboard using pyperclip
        pyperclip.copy(content)  # Copy the content to clipboard
        
        # Paste content from clipboard into the input box
        input_box.send_keys(Keys.CONTROL, 'v')  # Simulate Ctrl+V to paste
        time.sleep(2)
        
        # Click the "Detect AI" button
        detect_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='aidr-primary-cta']"))
        )
        detect_button.click()
        time.sleep(3)
        
        # Wait for AI Result
        ai_percentage_element = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.CLASS_NAME, "css-1xb5foi"))
        )
        ai_percentage = ai_percentage_element.text.strip()
        
        driver.quit()
        return ai_percentage if ai_percentage else "Error retrieving AI detection result."
    except Exception as e:
        driver.quit()
        return f"Error: {str(e)}"

# Function to create the Excel report
def create_excel_report(url, content, word_count, ai_result):
    # Create a DataFrame
    data = {
        "URL": [url],
        "Content": [content],
        "Word Count": [word_count],  # Use the word count from session_state
        "AI Content Result": [ai_result]
    }
    df = pd.DataFrame(data)
    
    # Save DataFrame to an Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Report")
    output.seek(0)
    return output

# Streamlit app code
st.title("Web Content Scraper & AI Detector")

# Initialize session state
if 'scraped_content' not in st.session_state:
    st.session_state.scraped_content = ""
if 'word_count' not in st.session_state:
    st.session_state.word_count = 0
if 'ai_result' not in st.session_state:
    st.session_state.ai_result = ""

# Get URL input
url = st.text_input("Enter a blog URL:")

if url:
    with st.spinner("Scraping content..."):
        # Scrape the content from the URL
        st.session_state.scraped_content = scrape_blog_content(url)
    
    # Display scraped content
    st.text_area("Scraped Content:", st.session_state.scraped_content, height=300)
    
    # Clean the scraped content by removing extra spaces and newlines
    cleaned_content = ' '.join(st.session_state.scraped_content.split())
    
    # Now count the words by splitting the cleaned content
    st.session_state.word_count = len(cleaned_content.split())
    st.write(f"Word Count: {st.session_state.word_count}")
    
    if st.button("Check AI Content"):
        with st.spinner("Analyzing AI detection..."):
            st.session_state.ai_result = detect_ai_content(st.session_state.scraped_content)
        st.write(f"AI Detection Result: {st.session_state.ai_result}")
    
    # Download Report Button
    if st.button("Download Report"):
        if not st.session_state.ai_result:
            st.warning("Please check AI content first before downloading the report.")
        else:
            with st.spinner("Generating report..."):
                # Generate the Excel report
                excel_file = create_excel_report(
                    url,
                    st.session_state.scraped_content,
                    st.session_state.word_count,
                    st.session_state.ai_result
                )
                # Provide a download button for the Excel report
                st.download_button(
                    label="Download Excel Report",
                    data=excel_file,
                    file_name="web_content_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
