import os

# Set before `app` is imported: real environment variables win over .env, and "test" skips
# the development camera seed, so tests that never touch the database don't need one.
os.environ["ENVIRONMENT"] = "test"
