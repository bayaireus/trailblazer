import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# OpenAI Client
client = OpenAI()

# Selenium setup
chrome_driver_path = "./chromedriver"
chrome_options = Options()
chrome_options.add_argument("--start-maximized")

# Set up Selenium WebDriver
service = Service(chrome_driver_path)
driver = webdriver.Chrome(service=service, options=chrome_options)

def is_browser_open():
    try:
        # This command checks if the browser session is still active
        driver.title
        return True
    except Exception:
        return False


# Function to wait for manual login
def wait_for_manual_login(target_url):
    print("Please log in manually.")
    print("Waiting for navigation to the target URL...")

    try:
        wait = WebDriverWait(driver, 300)
        wait.until(lambda d: d.current_url.startswith(target_url))
        print("Target URL reached! Type 'START' to begin.")
    except TimeoutException:
        print("Timeout: Did not reach the target URL.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# Function to extract article text
def extract_article_text():
    try:
        print("Extracting article content...")
        article = driver.find_element(By.CSS_SELECTOR, "article.slds-large-size_9-of-12.slds-size_12-of-12.slds-col.slds-order_1")
        text_content = article.text
        print("Article content extracted successfully.")
        return text_content
    except NoSuchElementException:
        print("Article not found on the page.")
        return None

# Function to query OpenAI for the best answer
def query_openai(question_text, options_text):
    print("Sending question and answers to OpenAI...")
    formatted_prompt = f"""
    Answer the following question based on the provided options:

    Question: {question_text}

    Options:
    {options_text}

    Respond with the letter (A, B, C, etc.) corresponding to the correct option.
    """
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides the best answer for quiz questions."},
                {"role": "user", "content": formatted_prompt}
            ]
        )
        result = completion.choices[0].message.content.strip()
        print(f"OpenAI Response: {result}")
        return result
    except Exception as e:
        print(f"Error querying OpenAI: {e}")
        return None

# Function to handle quiz interaction
def handle_quiz():
    try:
        if not is_browser_open():
            print("Browser is closed. Cannot handle the quiz.")
            return

        print("Locating the quiz container using direct DOM queries...")

        # Use JavaScript to directly access the shadow root and fetch questions and options
        questions_and_options = driver.execute_script("""
            const shadowHost = document.querySelector('th-enhanced-quiz');
            const shadowRoot = shadowHost.shadowRoot.querySelector('th-tds-enhanced-quiz').shadowRoot;
            const questions = Array.from(shadowRoot.querySelectorAll('div.question'));
            
            return questions.map(question => {
                const questionText = question.querySelector('legend').innerText.trim();
                const options = Array.from(question.querySelectorAll('div.option')).map(option => ({
                    letter: option.querySelector('div.option-letter').innerText.trim(),
                    text: option.querySelector('div.option-text')?.innerText.trim() || '',
                    input: option.querySelector('input.option-input')
                }));
                return { questionText, options };
            });
        """)

        if not questions_and_options:
            print("No quiz questions found.")
            return

        print(f"Found {len(questions_and_options)} questions.")

        for index, qa in enumerate(questions_and_options):
            if not is_browser_open():
                print("Browser is closed. Stopping quiz handling.")
                break

            question_text = qa['questionText']
            options = qa['options']

            print(f"\nQuestion {index + 1}: {question_text}")

            options_text = ""
            option_mapping = {}
            for option in options:
                options_text += f"{option['letter']}: {option['text']}\n"
                option_mapping[option['letter']] = option['input']

            print("Options:")
            print(options_text)

            # Send question and options to OpenAI
            best_answer = query_openai(question_text, options_text)

            # Parse OpenAI response to isolate the letter
            if best_answer:
                best_answer_letter = best_answer.split(":")[0].strip()  # Extract "A" from "A: True" or "The correct option is A"
                best_answer_letter = best_answer_letter.replace("The correct option is", "").strip()  # Handle verbose responses

                # Select the best answer
                if best_answer_letter in option_mapping:
                    answer_input = option_mapping[best_answer_letter]
                    driver.execute_script("arguments[0].click();", answer_input)
                    print(f"Selected option: {best_answer_letter}")
                else:
                    print(f"No matching answer found for: {best_answer_letter}")
            else:
                print("No response from OpenAI.")

        # Click the "Check the Quiz" button
        print("Clicking the 'Check the Quiz' button...")
        try:
            WebDriverWait(driver, 10).until(lambda d: d.execute_script("""
                const shadowHost = document.querySelector('th-enhanced-quiz');
                const shadowRoot = shadowHost.shadowRoot.querySelector('th-tds-enhanced-quiz').shadowRoot;
                const button = shadowRoot.querySelector('th-tds-button.footer-button');
                if (button) {
                    button.click();
                    return true;
                }
                return false;
            """))
            print("Quiz checked successfully.")
        except TimeoutException:
            print("Failed to click 'Check the Quiz' button: Button not found.")

    except Exception as e:
        print(f"An error occurred while handling the quiz: {e}")

# Function to move to the next unit
def proceed_to_next_unit():
    try:
        print("Checking for 'Tackle the next unit' button...")
        next_unit_button = WebDriverWait(driver, 15).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "button.slds-button.slds-button_brand.tds-button_brand")
        )
        next_unit_button.click()
        print("Moved to the next unit.")
        return True
    except TimeoutException:
        print("No 'Tackle the next unit' button found.")
        return False

# Main loop
def main_loop():
    while True:
        if not is_browser_open():
            print("Browser is closed. Exiting script.")
            break

        user_input = input("Enter a command (START/STOP/EXIT): ").strip().upper()

        if user_input == "START":
            while True:  # Loop for handling consecutive units
                if not is_browser_open():
                    print("Browser is closed. Exiting script.")
                    break

                # Extract article content
                article_text = extract_article_text()
                if article_text:
                    print("Article content extracted. Starting quiz handling...")
                    handle_quiz()

                    # Proceed to the next unit
                    if not proceed_to_next_unit():
                        print("No more units found. Returning to idle state.")
                        break  # Break the inner loop, wait for user input
                else:
                    print("No article found. Returning to idle state.")
                    break  # Break the inner loop, wait for user input

        elif user_input == "STOP":
            print("Script paused. Type START to resume or EXIT to quit.")
        elif user_input == "EXIT":
            print("Exiting script. Please close the browser manually.")
            break
        else:
            print("Invalid command. Type 'START' to begin, 'STOP' to idle, or 'EXIT' to quit.")


if __name__ == "__main__":
    try:
        LOGIN_URL = "https://tbid.digital.salesforce.com/"
        TARGET_URL = "https://www.salesforce.com/trailblazer/profile/"

        # Open the login page
        print("Opening the login page...")
        driver.get(LOGIN_URL)

        # Wait for the user to log in manually
        wait_for_manual_login(TARGET_URL)

        # Start the main loop
        main_loop()

    except KeyboardInterrupt:
        print("\nScript interrupted by user.")

    finally:
        print("Script ended. Browser is still open.")
