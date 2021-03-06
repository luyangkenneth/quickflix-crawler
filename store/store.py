'''
DB Management
---------------
'''

import logging
import mongo
from bson.objectid import ObjectId
import pymongo

import json
import requests

log = logging.getLogger(__name__)

COLLECTIONS = ['movies', 'reviews', 'queue', 'visited', 'links', 'visitedDomain']

# update visisted domain info
def update_visited_domain(domain, success):
    db = mongo.get_db()
    find_domain = db.visitedDomain.find_one({'domain':domain})
    success_incremental_value = 1 if success else 0
    if find_domain:
        db.visitedDomain.update_one(
        {'domain':domain},
        {'$inc': {'total':1,'success': success_incremental_value}}, upsert=False)
    else:
        db.visitedDomain.insert_one({'domain':domain, 'total':1, 'success': success_incremental_value})


def should_visit_domain(domain):
    db = mongo.get_db()
    find_domain = db.visitedDomain.find_one({'domain':domain})
    if find_domain:
        total = find_domain['total']
        success = find_domain['success']
        if success == 0 and total > 500 or success*1.0/total < 0.00001:
            return False
    return True

# Clears all data from db
def empty_db():
    db = mongo.get_db()
    for collection in COLLECTIONS:
        db[collection].delete_many({})

# Adds movie title and info into db
def add_movie(movie_title, movie_info):
    db = mongo.get_db()
    exist = db.movies.find_one({'title': movie_title})
    if exist:
        return None
    else:
        item_id = db.movies.insert_one({'title': movie_title, 'info': movie_info}).inserted_id
        return item_id


# Returns a list of all movie titles
def get_movies():
    db = mongo.get_db()
    movies = list(db.movies.find())
    if movies:
        for i, item in enumerate(movies):
            movies[i] = item['title']
    return movies

# Returns movie info for a particular movie
def get_movie_info(movie_titie):
    db = mongo.get_db()
    movies = list(db.movies.find({'title': movie_title}))
    if movies:
        return movies[0]['info']
    else:
        log.info("No info found for " + movie_title)
        return None

# Returns a json with the movie info, fetched from omdbapi.com
def retrieve_movie_info(movie_title):
    processed_name = movie_title.replace(" ", "+")
    try:
        # query_link = "http://www.omdbapi.com/?t=" + processed_name + "&y=&plot=full&r=json"
        url = "http://www.omdbapi.com"
        params = {
            't': processed_name,
            'plot': 'short',
            'r' : 'json'
        }
        res = requests.get(url=url, params=params)
        movie_info = json.loads(res.text)
        return movie_info
    except ValueError as e:
        log.info(movie_title + ' info cannot be parsed')
        return None
    except requests.exceptions.RequestException as e:
        log.info(movie_title + ' info cannot be retrieved')
        return None

# Adds review into db
def add_review(review):
    db = mongo.get_db()

    # If movie title is not already in db.movies, retrieve movie info and add it
    movie_title = review['itemReviewed']['name']
    movies = list(db.movies.find({'title': movie_title}))
    if not movies:
        # Add into db.movies only when movie info is available
        # This means that if retrieving movie info is unsuccessful, there might be reviews of the movie in db.reviews, but no record of the movie title and info in db.movies
        movie_info = retrieve_movie_info(movie_title)
        if movie_info is not None:
            add_movie(movie_title, movie_info)

    # Check for duplicate reviews for the same movie
    existing_reviews = get_reviews(movie_title)
    for possible_duplicate in existing_reviews:
        if review['url'] == possible_duplicate['url']:
            log.info('Review already added into database')
            return None

    # Add review into db.reviews
    review['rank'] = 0 # give initial pageRank
    item_id = db.reviews.insert_one(review).inserted_id
    if item_id == 0:
        log.error("Unable to add review")
        return None
    return item_id

# Returns a list of all reviews (json objects) for a particular movie
def get_reviews(movie_title):
    db = mongo.get_db()
    reviews = list(db.reviews.find({'itemReviewed.name': movie_title}))
    if not reviews:
        # Returns an empty dictionary instead of returning None
        log.info("No reviews found for " + movie_title)
    return reviews

def queue_push(url, priority=1):
    db = mongo.get_db()
    item_id = db.queue.insert_one({'url': url, 'priority': priority}).inserted_id
    if item_id == 0:
        log.error("Unable to add URL into queue")
        return None
    return item_id

def queue_pop():
    db = mongo.get_db()
    MAX_PRIORITY = 2
    priority = 0

    item = db.queue.find_one_and_delete({}, sort=[('priority', pymongo.ASCENDING)])
    if item is not None:
        # db.queue.delete_one({'_id': ObjectId(item['_id'])})
        return item['url'], item['priority']
    else:
        return None, None

def add_to_visited(url):
    db = mongo.get_db()
    item_id = db.visited.insert_one({'url': url}).inserted_id
    if item_id == 0:
        log.error("Unable to add URL into visited")
        return None
    return item_id

def get_visited():
    db = mongo.get_db()
    visited = list(db.visited.find())
    if visited:
        for i, item in enumerate(visited):
            visited[i] = item['url']
    return visited

def add_outgoing_links(url, outgoing_links):
    db = mongo.get_db()
    item_id = db.links.insert_one({'key': url, 'links': outgoing_links}).inserted_id

def get_outgoing_links():
    db = mongo.get_db()
    return list(db.links.find())

def updatePageRank(url, rank):
    db = mongo.get_db()
    db.reviews.update_one({'url': url}, {'$set': {'rank': rank}})
