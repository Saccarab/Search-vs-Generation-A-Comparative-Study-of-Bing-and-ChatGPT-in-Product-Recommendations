import sqlite3
import pandas as pd
from flask import Flask, render_template_string, request
import json
import os

# ... (Templates and other code) ...

# I will read the file and then write the whole thing back with changes.
# But since I can't read the whole file in one go if it's too big, 
# I'll use search_replace on smaller chunks.
