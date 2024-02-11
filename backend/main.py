




from starlette.responses import JSONResponse
from typing import List
import pymongo
from fastapi import FastAPI, HTTPException
import requests
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,HttpUrl
from openai import OpenAI
import base64
import re
from typing import Dict
import random


class Project(BaseModel):
    name: str
    description: str
    github_url: str

class UserData(BaseModel):
    username: str
    skills: List[str]
    projects: List[Project]
    college_name: str

class GitHubURL(BaseModel):
    url: str

class UserRequest(BaseModel):
    username: str
    token: str  # Token is used for demonstration; use secure methods in real applications.

class RepoUrl(BaseModel):
    url: HttpUrl  

class Issue(BaseModel):
    title: str
    url: str
    description: str
    stars: int

class IssueURL(BaseModel):
    issue_url: HttpUrl

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

categories = [
    "good_first_issue",
    "help_wanted",
    "enhancement",
    "bug",
    "documentation",
    "question",
    "wontfix",
    "duplicate",
    "invalid",
    "important"
]

def get_user_languages_with_byte_count(username: str, token: str) -> dict:
    headers = {'Authorization': f'token {token}'}
    repos_url = f'https://api.github.com/users/{username}/repos'
    repos_response = requests.get(repos_url, headers=headers)
    if repos_response.status_code != 200:
        return None
    repos = repos_response.json()
    
    language_data = {}
    for repo in repos:
        languages_url = repo['languages_url']
        languages_response = requests.get(languages_url, headers=headers)
        languages = languages_response.json()
        for language, bytes_count in languages.items():
            language_data[language] = language_data.get(language, 0) + bytes_count
    
    return language_data

def find_open_source_projects(language: str, token: str) -> list:
    headers = {'Authorization': f'token {token}'}
    search_url = f"https://api.github.com/search/repositories?q=language:{language}&sort=stars&order=desc"
    response = requests.get(search_url, headers=headers)
    if response.status_code != 200:
        return None
    projects = response.json()['items'][:5]
    return [{
        "name": project['name'],
        "html_url": project['html_url'],
        "description": project['description'],
        "stars": project['stargazers_count']
    } for project in projects]

def fetch_issues_by_category(language: str, category: str, token: str) -> list:
    headers = {'Authorization': f'token {token}'}
    search_url = f"https://api.github.com/search/issues?q=language:{language}+label:\"{category}\"+state:open&sort=created&order=desc"
    response = requests.get(search_url, headers=headers)
    if response.status_code != 200:
        return None
    issues = response.json()['items'][:5]
    return [{
        "title": issue['title'],
        "html_url": issue['html_url'],
        "repository_url": issue['repository_url'],
        "created_at": issue['created_at']
    } for issue in issues]

def fetch_issues_for_all_categories(language: str, token: str) -> dict:
    all_category_issues = {}
    for category in categories:
        category_issues = fetch_issues_by_category(language, category, token)
        if category_issues:
            all_category_issues[category] = category_issues
    return all_category_issues

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/category-recommendations/{username}")
def read_all_category_recommendations(username: str, token: str):
    # myclient = pymongo.MongoClient("mongodb+srv://root:root@ipd.zfgiflr.mongodb.net/")
    # mydb = myclient["user"]
    # mycol = mydb["deepgohil"]
    languages_with_byte_count = get_user_languages_with_byte_count(username, token)
    if languages_with_byte_count is None:
        raise HTTPException(status_code=404, detail="User not found or error fetching repositories")
    
    favorite_language = max(languages_with_byte_count, key=languages_with_byte_count.get)
    all_category_issues = fetch_issues_for_all_categories(favorite_language, token)
    if all_category_issues is None or not all_category_issues:
        raise HTTPException(status_code=500, detail="Error fetching issues across categories")
    # document = {
    #     "username": username,
    #     "favorite_language": favorite_language,
    #     "category_issues": all_category_issues
    # }
    # mycol.insert_one(document)
    return {"username": username,
        "favorite_language": favorite_language,
        "category_issues": all_category_issues}




@app.get("/latest-open-source-issues/")
def get_latest_open_source_issues(language: str = "Python",GITHUB_TOKEN: str='GITHUB_TOKEN'):
    
    GITHUB_API_URL = "https://api.github.com/search/issues"
    MAX_RESULTS = 10  # Target number of results
    items_per_page = 20  # Max items GitHub allows per page
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    params = {
        "q": f"language:{language} is:issue is:open stars:>50",
        "sort": "created",
        "order": "desc",
        "per_page": items_per_page,
        "page": 1
    }
    all_results = []
    
    while len(all_results) < MAX_RESULTS:
        response = requests.get(GITHUB_API_URL, headers=headers, params=params)
        if response.status_code == 200:
            issues = response.json()['items']
            if not issues:
                break  # Break if no more issues are found
            for issue in issues:
                repo_url = issue['repository_url']
                repo_response = requests.get(repo_url, headers=headers)
                if repo_response.status_code == 200:
                    repo_data = repo_response.json()
                    if repo_data['stargazers_count'] > 50:
                        all_results.append({
                            "issue_title": issue['title'],
                            "issue_url": issue['html_url'],
                            "stars": repo_data['stargazers_count'],
                            "language": repo_data['language'],
                            "contribution_link": f"{repo_data['html_url']}/blob/master/CONTRIBUTING.md"
                        })
                    if len(all_results) >= MAX_RESULTS:
                        break
            params["page"] += 1  # Increment the page parameter for pagination
        else:
            raise HTTPException(status_code=response.status_code, detail="Error fetching issues from GitHub API")
    
    return all_results[:MAX_RESULTS]  # Ensure we return only up to MAX_RESULTS items


@app.post("/fetch-user-data/")
def fetch_user_data(request: UserRequest):
    headers = {"Authorization": f"token {request.token}"}
    repos_url = f"https://api.github.com/users/{request.username}/repos?per_page=100&type=all"
    repos_response = requests.get(repos_url, headers=headers)
    if repos_response.status_code != 200:
        raise HTTPException(status_code=repos_response.status_code, detail="Failed to fetch repositories")

    repos = repos_response.json()
    repo_details = [{"name": repo['name'], "html_url": repo['html_url']} for repo in repos]

    contributions = []
    for repo in repo_details:
        commits_url = f"https://api.github.com/repos/{request.username}/{repo['name']}/commits?author={request.username}"
        commits_response = requests.get(commits_url, headers=headers)
        if commits_response.status_code == 200:
            commit_count = len(commits_response.json())
            contributions.append({"repo_name": repo['name'], "commit_count": commit_count, "repo_url": repo['html_url']})

    return {
        "repositories": repo_details,
        "contributions": contributions
    }


@app.post("/get-repo-owner/")
def get_repo_owner(repo_url: RepoUrl, token: str):
    """
    Extracts the owner's name from a given GitHub repository URL.
    """
    # Extract the repository's owner and name from the URL
    path_segments = repo_url.url.path.split('/')
    if len(path_segments) < 3:
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
    
    owner, repo_name = path_segments[1], path_segments[2]

    # Use the GitHub API to fetch the repository details
    headers = {'Authorization': f'token {token}'}
    repo_api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
    response = requests.get(repo_api_url, headers=headers)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch repository details from GitHub")

    repo_details = response.json()
    return {"owner_name": repo_details['owner']['login']}

@app.get("/top-ml-repos/")
def get_top_ml_repos(language: str = "Python", topic: str = "machine-learning", top_n: int = 5):

    base_url = "https://api.github.com/search/repositories"
    query = f"q=language:{language}+topic:{topic}&sort=stars&order=desc"
    response = requests.get(f"{base_url}?{query}&per_page={top_n}")
    
    if response.status_code == 200:
        search_results = response.json()
        repos = search_results['items']
        top_repos = [{
            'name': repo['name'],
            'html_url': repo['html_url'],
            'description': repo['description'],
            'stars': repo['stargazers_count']
        } for repo in repos]
        return top_repos
    else:
        return {"error": "Failed to fetch repositories from GitHub"}


@app.get("/get-user-data/{username}")
def get_user_data(username: str):
    # MongoDB connection details
    MONGO_URL = "mongodb+srv://root:root@ipd.zfgiflr.mongodb.net/"
    DB_NAME = "user"
    COLLECTION_NAME = "deepgohil"

    # Initialize MongoDB client and select database and collection
    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    user_data = collection.find_one({"username": username}, {"_id": 0})  # Exclude the MongoDB ID from the result
    if user_data:
        return user_data
    else:
        raise HTTPException(status_code=404, detail="User not found")
    



@app.get("/latest-open-source-issues-fromdbs/", response_model=List[dict])
def read_items():
    MONGO_URL = "mongodb+srv://root:root@ipd.zfgiflr.mongodb.net/"
    DB_NAME = "user"
    COLLECTION_NAME = "latest-open-source-issues"

    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    items = list(collection.find({}, {'_id': 0}))  # Excluding the '_id' field from the results
    return items
import json
@app.post("/fetch-user-data-fromdbs/")
def fetch_user_data(request: UserRequest):
    try:
    # Open the JSON file and load its content
        with open("profile.json", "r") as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        # Return an error message if the file is not found
        return {"error": "Profile data not found."}



@app.post("/get-mails/")
def get_username_from_issue_url(issue_url: IssueURL):
    # Extract the path from the URL
    path_segments = issue_url.issue_url.path.split('/')
    # The username is expected to be the second segment in the path,
    # given the structure: /owner/repository/issues/number
    if len(path_segments) >= 3:
        username = path_segments[1]
        url = f"https://api.github.com/users/{username}/events/public"
        response = requests.get(url)
        data = response.json()
        emails = []

        # Iterate through each event in the response
        for event in data:
            # Check if the event has a 'payload' key and 'commits' within the payload
            if 'payload' in event and 'commits' in event['payload']:
                # Iterate through each commit in the payload
                for commit in event['payload']['commits']:
                    # Check if the commit has an 'author' key and 'email' within the author
                    if 'author' in commit and 'email' in commit['author']:
                        # Add the email to the list of emails
                        email = commit['author']['email']
                        if email not in emails:  # Avoid duplicating emails
                            emails.append(email)       
        return {"emails": emails}
    else:
        raise HTTPException(status_code=400, detail="Invalid issue URL format.")
    
class Prompt(BaseModel):
    content: str

# Make sure to set your OPENAI_API_KEY in your environment variables




@app.post("/get-ai-response/")
def get_openai_response(prompt: Prompt):
    api_key = "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"
    client = OpenAI(api_key=api_key)
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt.content,
                }
            ],
            model="gpt-3.5-turbo",
        )

        if chat_completion.choices:
            response_message = chat_completion.choices[0].message.content
            print(type(response_message))
            github_urls = re.findall(r'https://github\.com/[a-zA-Z0-9-]+/[a-zA-Z0-9-]+', response_message)

            return {"response": response_message, "github_urls": github_urls}
        else:
            return {"response": "No response was generated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get-readme/")
def get_readme(github_url: GitHubURL):
    api_key = "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"
    client = OpenAI(api_key=api_key)
    try:
        split_url = github_url.url.split("/")
        owner = split_url[3]
        repo = split_url[4]
    except IndexError:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL format.")

    # GitHub API endpoint to get the README.md content
    api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"

    # Making a request to the GitHub API
    response = requests.get(api_url)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch README.md")

    # Extracting the content of README.md and decoding it
    readme_data = response.json()
    readme_content = base64.b64decode(readme_data['content']).decode('utf-8')
    chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": readme_content+"             explain me this in simple words",
                }
            ],
            model="gpt-3.5-turbo",
        )
    if chat_completion.choices:
            response_message = chat_completion.choices[0].message.content

    return {"readme_content": response_message}

@app.get("/leaderboard/")
def leaderboard():
    users = ["deep", "shashwat", "riya", "neha", "tejas", "khushi"]
    user_numbers: Dict[str, int] = {user: random.randint(1, 15) for user in users}
    sorted_users = sorted(user_numbers.items(), key=lambda item: item[1], reverse=True)
    sorted_user_numbers: Dict[str, int] = {user: number for user, number in sorted_users}
    sorted_user_list: List[Dict[str, int]] = [{"name": user, "number": number} for user, number in sorted_users]

    return sorted_user_list

@app.get("/search/")
def search_repos(domain: str, GITHUB_TOKEN: str):
    # try:
    # # Open the JSON file and load its content
    #     with open("domainsearch.json", "r") as file:
    #         data = json.load(file)
    #     return data
    # except FileNotFoundError:
    #     # Return an error message if the file is not found
    #     return {"error": "Profile data not found."}

    url = "https://api.github.com/search/repositories"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    params = {
        "q": f"topic:{domain}",
        "sort": "stars",
        "order": "desc"
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        items = data["items"][:4]  # Get only the top 5 repositories
        
        # Extract only the required information
        simplified_data = [{
               "repository_title": item["name"], 
            "repository_url": item["html_url"],
            "topics": item["topics"] if "topics" in item else [],
            "stargazers_count": item["stargazers_count"]
        } for item in items]
        
        return simplified_data
    except requests.RequestException as e:
        status_code = e.response.status_code if e.response else 500
        return JSONResponse(content={"message": str(e)}, status_code=status_code)




def save_user_data(user_data: UserData):
    MONGO_URL = "mongodb+srv://root:root@ipd.zfgiflr.mongodb.net/"
    DB_NAME = "user"
    
    # Convert Pydantic model to dictionary and remove username for document
    data_dict = user_data.dict()
    username = data_dict.pop("username")
    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]
    collection = db[username]
    collection.insert_one(data_dict)

@app.post("/submit-data/")
def submit_data(data: UserData):
    save_user_data(data)
    return {"message": "Data received successfully", "username": data.username}


@app.get("/getdata/")
def read_items( username:str):
    MONGO_URL = "mongodb+srv://root:root@ipd.zfgiflr.mongodb.net/"
    DB_NAME = "user"
    

    client = pymongo.MongoClient(MONGO_URL)
    db = client[DB_NAME]
    collection = db[username]
    items = list(collection.find({}, {'_id': 0}))  # Excluding the '_id' field from the results
    return items


@app.post("/get-ai-project/")
def get_openai_response(prompt: Prompt):
    api_key = "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"
    client = OpenAI(api_key=api_key)
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt.content+"suggest me brojects based on this my favourite programming language is python",
                }
            ],
            model="gpt-3.5-turbo",
        )

        if chat_completion.choices:
            response_message = chat_completion.choices[0].message.content
            print(type(response_message))


            return {"response": response_message}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))