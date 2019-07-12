from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.by import By
import time
import re
import json

''' 
This is a data extractor for Zomato site

supposed human flow
====================
1. Open the restaurants page in Zomato
2. Choose only restaurants that has the 'order now' buttons active and loop on them ignoring the rest
3. Get each restaurant name, address, hours, cuisine
4. click on the 'Order Now' button for each restaurant and get the list of meals for the restaurant
5. repeat the same process for all pages
'''
# ----------variables initialization ----------------#
city = "dubai"  # can be turned into a list of cities later on
time_limit = 30
interrupted = True  # set this flag to true if the scrabbing was interrupted and run it again
result_file_path = './restaurants_data.txt'
if interrupted:
    dump_file = open(result_file_path, 'a')  # append to file if there was interruption
else:
    dump_file = open(result_file_path, 'w')  # write a new file if there was no interruption
dump_file.write('[')  # writing '[' to the file as we will need it to contain jsonified array of objects
dump_file.close()
check_point_page = 1  # initializing the checkpoint page variable with 1 in case there were no interruptions
check_point_restaurant = 0  # initializing the checkpoint restaurant variable with 1 in case there were no interruptions
get_restaurants_with_meals_only = False  # flag to get restaurants where we have meals in text not image
restaurant_order = 1  # initializing the variable that will has the restaurant number per page
restaurant_check_point = 1  # initializing the variable that will load the restaurant number per page when interrupted


# ----------classes and functions initialization ----------------#


class NoneObject:
    """this class will be used when we need an object whose attribute "text" gives 'None' """
    def __init__(self):
        self.text = 'None'


def restaurants_per_page(page_num, check_point_restaurant):
    """this function gets the restaurants data in a jsonified manner per page"""
    print("starting from page", page_num, "and restaurant", check_point_restaurant)
    try:  # Wait until the needed rendered components are loaded within 10 seconds time limit
        element = WebDriverWait(driver, time_limit).until(
            ec.presence_of_element_located((By.CLASS_NAME, "search-card")))
    except:
        print("Couldn't load new page within the time limit")
    containers_per_page = driver.find_elements_by_class_name(
        'search-card')  # get a list of cards that has restaurants info
    # Narrowing the scope of working from the whole page to the containers context
    restaurant_order = 0
    for container in containers_per_page:
        restaurant_order += 1  # Increasing order as we found restaurants, this var will be our index
        # test the existence of the 'order now' button, this is a one item list
        menu_capable = container.find_elements_by_link_text("Order Now")
        if not menu_capable and get_restaurants_with_meals_only:  # if the menu capable list is empty, there is no 'order now' button, and we only want restaurants with meals skip this restaurant
            print("skipping this container as there is no menu in the text format for it \n")
            continue
        if interrupted:
            if restaurant_order <= check_point_restaurant:  # only start after the checkpoint restaurant otherwise skip
                print("skipping this restaurant as order is:", restaurant_order,"while checkpoint is at",check_point_restaurant)
                continue
        restaurant_name_per_container = container.find_element_by_class_name(
            'result-title').text  # get the restaurant name
        print("we are at scrabbable restaurant number", restaurant_order, "it's name is:",
              restaurant_name_per_container)
        restaurant_address_per_container = container.find_element_by_class_name(
            'search-result-address').text  # get address
        table_booking = container.find_elements_by_class_name(
            'table-booking-search')  # test existence of booking button
        if table_booking:
            table_booking = True
        else:
            table_booking = False
        restaurant_rate_per_container = container.find_elements_by_class_name('rating-popup')  # using a list to check if element is present or list will be empty instead of "try .. except" block
        if not restaurant_rate_per_container:
            restaurant_rate_per_container = [NoneObject()]  # using the none object to produce an attribute "text" of value None
        if re.match("^\d+?\.\d+?$", restaurant_rate_per_container[0].text) is None:  # using regex check if rate string is float
            restaurant_vote_per_container = None
        else:
            restaurant_vote_per_container = container.find_element_by_css_selector("span[class^='rating-votes-div']").text.strip(' votes')
        # get the info of the restaurants; hours, cuisines, promotions if there are any and book for two
        restaurant_info = container.find_element_by_class_name('search-page-text.clearfix.row').text
        restaurant_info = re.split(r"\.|\?|\!|\n|\r",
                                   restaurant_info)  # change it from string to list separated by lines

        restaurant_info_formatted = {'name': restaurant_name_per_container, 'address': restaurant_address_per_container,
                                     'table booking': table_booking, 'rate': restaurant_rate_per_container[0].text,
                                     'votes': restaurant_vote_per_container}
        for i in range(0, len(restaurant_info) - 1, 2):
            # changing info to a dict to be jsonfied later and making sure there are no ':' character
            restaurant_info_formatted[restaurant_info[i].strip(':')] = restaurant_info[i + 1]
        # ------------------------------- retrieving meals info -----------------------------------#
        if menu_capable:
            main_window = driver.window_handles[0]  # add a reference to main window 'restaurants page' here
            meals_per_restaurant = []  # a list that will be added later to the restaurants info dict
            menu_capable[0].send_keys(Keys.CONTROL + Keys.RETURN)  # open the menus in a new tab
            time.sleep(2)  # wait for the new tab to load
            menu_window = driver.window_handles[1]  # add a reference to menu window 'menu for selected restaurant here
            driver.switch_to.window(menu_window)  # switch focus to the new tab
            try:  # Wait until the needed rendered components are loaded within 10 seconds time limit
                element = WebDriverWait(driver, time_limit).until(
                    ec.presence_of_element_located((By.CLASS_NAME, "ui.item.item-view")))
            except:
                print("Couldn't load elements within the time limit")
            meals_objects = driver.find_elements_by_class_name("ui.item.item-view")
            for meal_per_restaurant in meals_objects:  # looping on the meals of the restaurant
                meal_details = {}  # dict for recording each meal details
                line_num_per_meal = 1  # initializing a counter
                for line in re.split(r"\.|\?|\!|\n|\r", meal_per_restaurant.text):  # looping on the details of each meal
                    # skip the test of 'add' and 'customizations available' buttons
                    if line.lower() == 'add' or line.lower() == 'customizations available':
                        continue
                    if line_num_per_meal == 1:  # first line has the name
                        meal_details['name'] = line.strip('\n')
                    elif line_num_per_meal == 2:  # second line has the price
                        meal_details['price'] = line.strip('\n')
                    else:  # third line has the description if it existed
                        meal_details['description'] = line.strip('\n')
                    line_num_per_meal += 1
                meals_per_restaurant.append(meal_details)
            # print("meals of this restaurant are:", meals_per_restaurant)
            driver.close()  # Close menu tab
            driver.switch_to.window(main_window)  # focus back to the previous restaurants page
        else:
            meals_per_restaurant = "image"
        restaurant_info_formatted['meals'] = meals_per_restaurant
        print(restaurant_info_formatted)
        # -------------------------------dumping data into files  ---------------------------------
        dump_file = open(result_file_path, 'a')  # appending to the file
        dump_file.write(json.dumps(restaurant_info_formatted))
        dump_file.write(",\n")
        dump_file.close()
        # recording the current restaurant order we have saved to be used as checkpoint later
        restaurant_check_point = open('restaurant_checkpoint.txt', 'w')
        restaurant_check_point.write(str(restaurant_order))
        restaurant_check_point.close()
        # -------------------------------- dump block ended ----------------------------------------

    print("finished scrapping", len(containers_per_page), "restaurants")


# ======= starting the program ===== #
if interrupted:  # something stopped the scrabber
    page_check_point = open('page_checkpoint.txt', 'r')
    for line in page_check_point:
        # get the stored number from the first line in the file to start from it after interruptions
        check_point_page = int(line)
    page_check_point.close()  # close the file
    restaurant_check_point = open('restaurant_checkpoint.txt', 'r')
    for line in restaurant_check_point:
        # get the stored number from the first line in the file to start from it after interruptions
        check_point_restaurant = int(line)
    restaurant_check_point.close()  # close the file


driver = webdriver.Firefox()  # the driver is now using firefox browser
driver.get("https://www.zomato.com/" + city + "/restaurants?q=restaurants&page="+str(check_point_page))
try:  # Wait until the needed components is loaded within 10 seconds time limit
    element = WebDriverWait(driver, time_limit).until(ec.presence_of_element_located((By.CLASS_NAME, "search-card")))
except:
    print("Couldn't load elements within the time limit")
pages_num = int(driver.find_element_by_class_name('col-l-4.mtop.pagination-number').text.split()[-1])  # total number of pages

for page_num in range(check_point_page, pages_num):  # start the loop after the checkpoint page
    if interrupted:  # if interrupted, start from checkpoint
        print(restaurants_per_page(page_num, check_point_restaurant))
    else:
        print(restaurants_per_page(page_num, 1))  # if not interrupted, start from one as normal
    interrupted = False  # toggling the flag back for the next iteration when checking if there is an interrupt
    try:  # Wait until the needed rendered components are loaded within 10 seconds time limit
        element = WebDriverWait(driver, time_limit).until(
            ec.presence_of_element_located((By.CLASS_NAME, "paginator_item.next.item")))
    except:
        print("couldn't find next page link")
    next_page = driver.find_element_by_class_name('paginator_item.next.item')  # locating next page button
    # saving the current page number in a file as a check point
    old_main_window = driver.window_handles[0]
    next_page.send_keys(Keys.CONTROL + Keys.RETURN)  # opening the next page in a new tab
    time.sleep(2)  # wait for the new tab to load
    next_main_window = driver.window_handles[1]
    driver.close()
    driver.switch_to.window(next_main_window)  # focusing on new window
    print("finished page:", page_num)
    # saving the new page as a checkpoint
    page_check_point = open('./page_checkpoint.txt', 'w')
    page_check_point.write(str(page_num+1))
    page_check_point.close()  # closing the checkpoint file
driver.quit()


dump_file = open(result_file_path, 'a')
dump_file.write(']')  # writing ']' to the file as we will need it to close jsonified array of objects
dump_file.close()

''' notes: 
1. if there are classes names separated by spaces then this means we see a child for example  class="op small"
 means that the class is a child of both 'op' class and 'small' class 

 2. Always work on rendered javascript page source to get all the elements, so always use 
 driver.execute_script("return document.body.innerHTML") or introduce a lot of time.sleep functions

 3. The find_element gives objects so we need to have .text attribute added to get the text
 '''
