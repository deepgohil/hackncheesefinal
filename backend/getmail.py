import requests

# Perform the GET request to the GitHub API
url = "https://api.github.com/users/Shashwatshah02/events/public"
response = requests.get(url)
data = response.json()

# Initialize an empty list to store emails
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

print(emails)
