cmake -S . -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DNUDEC_FETCH_KTX=ON \
    -DPython_EXECUTABLE="$(cd "$(dirname "$0")"/.. && pwd)/shelldelta_env/bin/python"