import asyncio
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
import psycopg2
from openpyxl import load_workbook
from playwright.async_api import async_playwright

# SENSITIVE VARIABLES
DB_URL = "db-url"
SENDER_EMAIL = "email"
SENDER_PASSWORD = "email-pass"
RECEIVER_EMAIL = "email"

DELAY = 1


async def checkPage(link):
    goodPage = False
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(link)
        await page.wait_for_timeout(5000)

        await page.wait_for_selector("h1.x-item-title__mainTitle", timeout=10000)

        outer_div = await page.query_selector("span.ux-timer__text")

        if outer_div:
            full_text = await outer_div.text_content()
            timer_text = full_text.replace("Ends in ", "").strip()

            if (
                ("h" in timer_text and "m" in timer_text)
                or ("m" in timer_text and "s" in timer_text)
                and "d" not in timer_text
            ):
                goodPage = True
        else:
            goodPage = True

        await browser.close()

    return goodPage


# Function to extract the listing names and prices using Playwright
async def getListings(url, keywords):
    names = []
    prices = []
    links = []
    pageCheck = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        await page.wait_for_timeout(10000)

        await page.wait_for_selector("div.s-item__wrapper.clearfix", timeout=10000)

        item_container = await page.query_selector("div.srp-river-results.clearfix")
        listings = await item_container.query_selector_all("div.s-item__info.clearfix")

        good_title = True
        i = 0
        for listing in listings:
            title_element = await listing.query_selector("div.s-item__title")
            title_text = await title_element.inner_text()
            if i < 2:
                pageCheck.append(title_text)
                i += 1

            for keyword in keywords:
                if keyword.lower() not in title_text.lower():
                    good_title = False

            if (
                "parts" in title_text.lower()
                or "repair" in title_text.lower()
                or "japan" in title_text.lower()
                or "read" in title_text.lower()
                or "issue" in title_text.lower()
                or "flaw" in title_text.lower()
            ):
                good_title = False

            price_element = await listing.query_selector("span.s-item__price")
            price_span = await price_element.query_selector("span.ITALIC")

            if price_span or "to" in (await price_element.inner_text()).strip()[1:]:
                good_title = False

            link_element = await listing.query_selector("a.s-item__link")
            href = await link_element.get_attribute("href")

            if good_title:
                if await checkPage(href):
                    price_int = float((await price_element.inner_text()).strip()[1:])
                    names.append(title_text)
                    prices.append(price_int)
                    links.append(href)

            good_title = True

        await browser.close()

        df = pd.DataFrame({"Name": names, "Price": prices, "Links": links})
        return df, pageCheck


# Returns the formatted URL with the filters enabled
def getUrl(search, price, pageNum):
    searchKey = ""
    search = search.split()
    for i in range(len(search)):
        if i < len(search) - 1:
            searchKey += f"{search[i]}+"
        else:
            searchKey += search[i]

    url = f"https://www.ebay.com/sch/i.html?_from=R40&_nkw={searchKey}&_sacat=0&LH_PrefLoc=1&LH_ItemCondition=3000&rt=nc&_udhi={price}&_pgn={pageNum}&imm=1"
    # print(url)
    return url


# This gets all of the Listing on the page and filters based on keywords
async def getAllListings(search, color, price, est_rev, monthly_drops, keywords):
    i = 1
    total_df = pd.DataFrame()

    url = getUrl(search, price, i)
    df, pageCheck1 = await getListings(url, keywords)
    df["color"] = color
    df["est_rev"] = est_rev
    df["monthly_drops"] = monthly_drops

    total_df = pd.concat([total_df, df], ignore_index=True)
    time.sleep(DELAY)

    while True:
        i += 1
        url = getUrl(search, price, i)
        # Await the call to `getListings` here too
        df, pageCheck2 = await getListings(url, keywords)
        df["color"] = color
        df["est_rev"] = est_rev
        df["monthly_drops"] = monthly_drops
        time.sleep(DELAY)

        if pageCheck1[0] == pageCheck2[0] or pageCheck1[1] == pageCheck2[1]:
            break
        else:
            total_df = pd.concat([total_df, df], ignore_index=True)
            pageCheck1 = pageCheck2

    total_df = total_df.drop_duplicates()
    return total_df


# This checks all the inventory items from the DB and sees what potential listings there are
async def checkAllInventory():
    # Connect to the PostgreSQL database
    connection = psycopg2.connect(DB_URL)

    # Create a cursor object
    cursor = connection.cursor()

    # Execute a query
    query = "SELECT * FROM inventory"
    cursor.execute(query)

    # Fetch all rows from the executed query
    rows = cursor.fetchall()

    total_df = pd.DataFrame()

    for row in rows:
        print(f"checking {row[0]}...")
        keywords = row[0].split()
        df = await getAllListings(row[0], row[1], row[2], row[3], row[4], keywords)
        total_df = pd.concat([total_df, df], ignore_index=True)

    cursor.close()
    connection.close()

    return total_df


# This sends an email of the potential listings to myself
def sendDF(df):
    html_table = df.to_html(index=False)

    # Create the email message
    msg = MIMEMultipart()

    now = datetime.now()
    current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")

    msg["Subject"] = f"Amazon Listings - {current_time_str}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    # Convert DataFrame to HTML
    html_table = df.to_html(index=False)

    # Create HTML body with the table
    html_content = f"""
    <html>
    <body>
    <p>Please find the table below:</p>
    {html_table}
    </body>
    </html>
    """

    # Attach the HTML content to the email
    msg.attach(MIMEText(html_content, "html"))

    # Send the email
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()  # Secure the connection
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
            print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")


# This saves a dataframe into a excel file that is stored locally
def saveDF(df):
    final_df = pd.DataFrame()
    final_df["name"] = df["Name"]
    final_df["color"] = df["color"]
    final_df["cost"] = df["Price"]
    final_df["est_rev"] = df["est_rev"]
    # final_df["profit"] = final_df["est_rev"] - final_df["cost"]
    # final_df["profit_margin"] = final_df["profit"] / final_df["est_rev"] * 100
    final_df["monthly_drops"] = df["monthly_drops"]
    final_df["url"] = df["Links"]

    file_path = "../../Reselling/inventory.xlsx"

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        final_df.to_excel(writer, index=False, sheet_name="Sheet1")

    workbook = load_workbook(file_path)
    sheet = workbook["Sheet1"]

    sheet.insert_cols(5)
    sheet.insert_cols(6)
    sheet["E1"] = "profit"
    sheet["F1"] = "profit_margin"

    rows = len(df) + 1  # +1 to account for the header row
    for row in range(2, rows + 1):  # Start from row 2 to skip the header
        sheet[f"E{row}"] = (
            f"=D{row}-C{row}"  # Formula for profit (E = est_rev - B = cost)
        )
        sheet[f"F{row}"] = (
            f"=E{row}/D{row}*100"  # Formula for profit_margin (E = profit / C = est_rev * 100)
        )

    # Save the Excel file after modifications
    workbook.save(file_path)
    print("Excel saved.")


if __name__ == "__main__":
    # df = checkAllInventory()
    df = asyncio.run(checkAllInventory())
    saveDF(df)
