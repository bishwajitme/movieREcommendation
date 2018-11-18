from flask import Flask, request, render_template, jsonify
from flask_restful import Resource, Api
from math import sqrt
import requests
from sqlalchemy import create_engine
import csv
import json
import pandas as pd


df = pd.read_csv('static/data/users.csv', sep=';')
user_list = df['UserName']
print(user_list)



ratings = {'Lisa': {'Lady in the Water': 2.5, 'Snakes on a Plane': 3.5,
                               'Just My Luck': 3.0, 'Superman Returns': 3.5, 'You, Me and Dupree': 2.5,
                               'The Night Listener': 3.0},
           'Gene': {'Lady in the Water': 3.0, 'Snakes on a Plane': 3.5,
                    'Just My Luck': 1.5, 'Superman Returns': 5.0, 'The Night Listener': 3.0,
                    'You, Me and Dupree': 3.5},
           'Mike': {'Lady in the Water': 2.5, 'Snakes on a Plane': 3.0,
                    'Superman Returns': 3.5, 'The Night Listener': 4.0},
           'Claudia': {'Snakes on a Plane': 3.5, 'Just My Luck': 3.0,
                       'The Night Listener': 4.5, 'Superman Returns': 4.0,
                       'You, Me and Dupree': 2.5},
           'Mick': {'Lady in the Water': 3.0, 'Snakes on a Plane': 4.0,
                    'Just My Luck': 2.0, 'Superman Returns': 3.0, 'The Night Listener': 3.0,
                    'You, Me and Dupree': 2.0},
           'Jack': {'Lady in the Water': 3.0, 'Snakes on a Plane': 4.0,
                    'The Night Listener': 3.0, 'Superman Returns': 5.0, 'You, Me and Dupree': 3.5},
           'Toby': {'Snakes on a Plane': 4.5, 'You, Me and Dupree': 1.0, 'Superman Returns': 4.0}}


app = Flask(__name__)
api = Api(app)


#USER BASED COLLABORATIVE FILTER


# Returns an Euclidean distance similarity score between person1 and person2
def sim_distance(prefs, person1, person2):
    # Get the list of shared_items
    si = {}
    for item in prefs[person1]:
        if item in prefs[person2]:
            si[item] = 1
    # if they have no ratings in common, return 0
    if len(si) == 0:
        return 0
    # Add the squares of all the differences
    sum_of_squares = sum([pow(prefs[person1][item] - prefs[person2][item], 2)
                          for item in prefs[person1] if item in prefs[person2]])
    return 1 / (1 + sum_of_squares)


# Returns the Pearson correlation coefficient between person1 and person2
def sim_pearson(prefs, person1, person2):
    # Get the list of mutually rated items
    si = {}
    for item in prefs[person1]:
        if item in prefs[person2]:
            si[item] = 1

    # Find the number of elements of the ratings dictionary
    n = len(si)

    # if they are no ratings in common, return 0
    if n == 0:
        return 0

    # Add up all the preferences from ratings
    sum1 = sum([prefs[person1][it] for it in si])
    sum2 = sum([prefs[person2][it] for it in si])

    # Sum of the squares
    sum1Sq = sum([pow(prefs[person1][it], 2) for it in si])
    sum2Sq = sum([pow(prefs[person2][it], 2) for it in si])

    # Sum of the products
    pSum = sum([prefs[person1][it] * prefs[person2][it] for it in si])

    # Calculate r Pearson score
    num = pSum - (sum1 * sum2 / n)
    den = sqrt((sum1Sq - pow(sum1, 2) / n) * (sum2Sq - pow(sum2, 2) / n))

    if den == 0:
        return 0

    r = num / den
    return r


# Returns the best matches for person from the ratings dictionary.
#Find the top matches using Euclidean distance as similarity measure

def topMatches(prefs, person, n=3, similarity=sim_distance):
    scores = [(similarity(prefs, person, other), other)
              for other in prefs if other != person]
    # Sort the list so the highest scores appear at the top
    scores.sort()
    scores.reverse()
    return scores[0:n]


# Returns the best matches for person from the ratings dictionary.
# Number of results and similarity function are optional params.
#In our case the similarity measure and number of results is fixed
# to Pearson correlation coefficient and 3 respectively


def bestMatcgByUser(prefs, person, n=3, similarity=sim_pearson):
    scores = [(similarity(prefs, person, other), other)
              for other in prefs if other != person]
    # Sort the list so the highest scores appear at the top
    scores.sort()
    scores.reverse()
    return scores[0:n]


# Gets recommendations for a person using a weighted average
# of every other user's rankings
def getRecommendations(prefs, person, similarity):
    totals = {}
    simSums = {}

    for other in prefs:  # type: object
        # don't compare me to myself
        if other == person:
            continue
        sim = similarity(prefs, person, other)

        # ignore scores of zero or lower
        if sim <= 0:
            continue
        for item in prefs[other]:

            # only score movies I haven't seen yet
            if item not in prefs[person] or prefs[person][item] == 0:
                # Similarity * Score
                totals.setdefault(item, 0)
                totals[item] += prefs[other][item] * sim
                # Sum of similarities
                simSums.setdefault(item, 0)
                simSums[item] += sim

    # Create the normalized list
    rankings = [(total / simSums[item], item) for item, total in totals.items()]

    # Return the sorted list
    rankings.sort()
    rankings.reverse()
    return rankings


# ITEM BASED FILTERING


#This function transform the data from user based to item based
#in our case we group the data using the names of the movies
#instead the name of users.
def transform_prefs(prefs):
    result = {}
    for person in prefs:
        for item in prefs[person]:
            result.setdefault(item, {})
            # Flip item and person
            result[item][person] = prefs[person][item]
    return result


def calculate_similar_items(prefs, n=10):
    # Create a dictionary of items showing which other items they
    # are most similar to.
    result = {}
    # Invert the preference matrix to be item-centric
    itemPrefs = transform_prefs(prefs)
    c = 0
    for item in itemPrefs:
        # Status updates for large datasets
        c += 1
        if c % 100 == 0:
            print "%d / %d" % (c, len(itemPrefs))
        # Find the most similar items to this one
        scores = topMatches(itemPrefs, item, n=n, similarity=sim_distance)
        result[item] = scores
    return result


#To run this function correctly we first need to transform the data
#using the transform preps then calculate similar items and finally
#run this function
def get_recommended_items(prefs, itemMatch, user):
    userRatings = prefs[user]
    scores = {}
    totalSim = {}

    # Loop over items rated by this user
    for (item, rating) in userRatings.items():
        # Loop over items similar to this one
        for (similarity, item2) in itemMatch[item]:
            # Ignore if this user has already rated this item
            if item2 in userRatings:
                continue
            # Weighted sum of rating times similarity
            scores.setdefault(item2, 0)
            scores[item2] += similarity * rating
            # Sum of all the similarities
            totalSim.setdefault(item2, 0)
            totalSim[item2] += similarity
        # Divide each total score by total weighting to get an average
        rankings = [(score / totalSim[item], item) for item, score in scores.items()]
        # Return the rankings from highest to lowest
    rankings.sort()
    rankings.reverse()
    return rankings


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/userbased')
def userbased():
    return render_template('userbased.html', userlist = user_list )

@app.route('/userbased/similaruser', methods=['GET'])
def get_matches():
    if 'name' in request.args:
           name = request.args['name']
    else:
        return "Error: You have not select any user to see the similarity."
    bestMatchUser = bestMatcgByUser(ratings, name, 3, sim_pearson)
    jsonify(bestMatchUser)
    return render_template('similaruser.html', result = bestMatchUser, username = name)


@app.route('/userbased/euclidean', methods=['GET'])
def get_euclidean():
    if 'name' in request.args:
       name = request.args['name']
    else:
       return "Error: You have not select any user to see the similarity."
    result = getRecommendations(ratings, name, sim_distance)
    jsonify(result)
    return render_template('euclidean.html', euresult = result, username = name)


@app.route('/userbased/pearson', methods=['GET'])
def get_pearson():
    if 'name' in request.args:
       name = request.args['name']
    else:
       return "Error: You have not select any user to see the similarity. Go back anf try again"
    peresults = getRecommendations(ratings, name, sim_pearson)
    jsonify(peresults)
    print peresults;
    return render_template('pearson.html', peresult = peresults, username = name)





@app.route('/itembased')
def itembased():
    return render_template('itembased.html', userlist = user_list )

@app.route('/itembased/similarity')
def similarity():
    if 'name' in request.args:
       name = request.args['name']
    else:
       return "Error: You have not select any user to see the similarity. Go back anf try again"
    transform_prefs(ratings)
    itemsim = calculate_similar_items(ratings, 4)
    resultItems = get_recommended_items(ratings, itemsim, name)
    return render_template('similarity.html', itemresult = resultItems, username = name)

if __name__ == '__main__':
    app.run(debug=True)
