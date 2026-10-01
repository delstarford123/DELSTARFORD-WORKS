import sys
import os

# Limit OpenBLAS and other multi-threaded libraries to 1 thread
# to prevent exceeding cPanel process/thread limits (RLIMIT_NPROC)
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"

# Add current folder to path
sys.path.insert(0, os.path.dirname(__file__))

# Import the Flask app object from main.py and expose it as 'application' for Phusion Passenger
from main import app as application

