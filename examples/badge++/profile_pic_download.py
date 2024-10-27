import requests
import shutil

def main():
    """
    Downloads the GitHub profile image of the specified user in different sizes.

    The function fetches the profile information of the user from the GitHub API,
    extracts the avatar URL, and downloads the profile image in various sizes.
    The images are saved in the current directory with filenames indicating their sizes.

    This script will need to be run on a machine with Internet access
    and a full operating system, not on the badger itself.
    """

    # TODO: Replace 'octocat' with the desired username
    username = 'octocat'
    response = requests.get(f'https://api.github.com/users/{username}')

    # Check if the request was successful
    if response.status_code == 200:
        # Get the image url from the response
        image_url = response.json().get('avatar_url')

        # Download images in different sizes
        sizes = ['086', '100', '114', '128']
        for size in sizes:
            request_url = f'{image_url}&size={size}'
            response = requests.get(request_url, stream=True)

            if response.status_code == 200:
                # Determine the file type.
                file_type = response.headers['Content-Type']
                if file_type == 'image/jpeg':
                    file_extension = 'jpg'
                elif file_type == 'image/png':
                    file_extension = 'png'
                else:
                    print(f'Unsupported file type: {file_type}')
                    continue

                with open(f'profile_{size}.{file_extension}', 'wb') as out_file:
                    shutil.copyfileobj(response.raw, out_file)
                response.raw.close()
            else:
                print(f'Failed to download image in size {size}.')


if __name__ == "__main__":
    main()
