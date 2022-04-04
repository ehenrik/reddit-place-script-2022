# Reddit Place Script 2022

## About

This is a script to draw an image onto r/place (<https://www.reddit.com/r/place/>).

## Features

- Support for multiple accounts.
- Detects existing matching pixels on the r/place map and skips them.
- Automatically converts colors to the r/place color palette.
- Easy(ish) to read output with colors.
- No client id and secret needed.
- Proxies from "proxies.txt" file.

## Get Started

Edit the file config.json

Edit the values to replace with actual credentials and values

Note: Please use https://jsonlint.com/ to check that your JSON file is correctly formatted

```json
{
	//Where the image's path is
	"image_path": "image.png",
	// [x,y] where you want the top left pixel of the local image to be drawn on canvas
	"image_start_coords": [741, 610],
	// delay between starting threads (can be 0)
	"thread_delay": 2,
	// array of accounts to use
	"workers": {
		// username of account 1
		"worker1username": {
			// password of account 1
			"password": "password",
			// which pixel of the image to draw first
			"start_coords": [0, 0], // the start coordinates are INCLUSIVE
			"stop_coords": [2, 20]  // the stop coordinates are EXCLUSIVE
		},
		// username of account 2
		"worker1username": {
			// password of account 2
			"password": "password",
			// which pixel of the image to draw first
			"start_coords": [2, 0],  // the start coordinates are INCLUSIVE
			"stop_coords": [4, 20]   // the stop coordinates are EXCLUSIVE
		}
		// etc... add as many accounts as you want (but reddit may detect you the more you add)
	}
}
```

## Run the Script

### Windows

```shell
start.bat or startverbose.bat
```

### Unix-like (Linux, MacOS etc.)

```shell
chmod +x start.sh startverbose.sh
./start.sh or ./startverbose.sh
```

**You can get more logs (`DEBUG`) by running the script with `-d` flag:**

`python3 main.py -d` or `python3 main.py --debug`

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:
>- Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.
>- Redistributions in binary form must reproduce the above
copyright notice, this list of conditions and the following disclaimer
in the documentation and/or other materials provided with the
distribution.
>- Neither the names of the copyright owners nor the names of its
contributors may be used to endorse or promote products derived from
this software without specific prior written permission.
>
>THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

## Docker

A dockerfile is provided. Instructions on installing docker are outside the scope of this guide.

To build: After editing the `config.json` file, run `docker build . -t place-bot`. and wait for the image to build.

You can now run it with `docker run place-bot`

## Contributing

See the [Contributing Guide](docs/CONTRIBUTING.md).
