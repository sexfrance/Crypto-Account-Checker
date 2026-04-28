<!-- SPONSOR-START -->
---

<div align="center">

### 🌐 Need Proxies? Check out my services

<a href="https://vaultproxies.com" target="_blank" rel="noopener noreferrer">
  <img src="https://i.imgur.com/TF165pP.gif" alt="VaultProxies">
</a>
<p></p>

<table>
  <tr>
    <th>Service</th>
    <th>Pricing</th>
    <th>Features</th>
  </tr>
  <tr>
    <td><b><a href="https://vaultproxies.com" target="_blank" rel="noopener noreferrer">🔮 VaultProxies</a></b></td>
    <td><code>$1.00/GB</code> residential</td>
    <td>Residential · IPv6 · Residential Unlimited · Datacenter</td>
  </tr>
  <tr>
    <td><b><a href="https://nullproxies.com" target="_blank" rel="noopener noreferrer">🌑 NullProxies</a></b></td>
    <td><code>$0.75/GB</code> residential</td>
    <td>Residential · Residential Unlimited · DC Unlimited · Mobile Proxies</td>
  </tr>
  <tr>
    <td><b><a href="https://strikeproxy.net" target="_blank" rel="noopener noreferrer">⚡ StrikeProxy</a></b></td>
    <td><code>$0.75/GB</code> residential</td>
    <td>Residential · Residential Unlimited · DC Unlimited · Mobile Proxies</td>
  </tr>
</table>
</div>

<!-- SPONSOR-END -->

<div align="center">
  <h2 align="center">Crypto.com Account Checker</h2>
  <p align="center">
    A PATCHED automated tool for checking Crypto.com accounts with proxy handling and multi-threading capabilities.
    <br />
    <br />
    <a href="https://discord.cyberious.xyz">💬 Discord</a>
    ·
    <a href="#-changelog">📜 ChangeLog</a>
    ·
    <a href="https://github.com/sexfrance/Crypto-Account-Checker/issues">⚠️ Report Bug</a>
    ·
    <a href="https://github.com/sexfrance/Crypto-Account-Checker/issues">💡 Request Feature</a>
  </p>
</div>

---

### ⚙️ Installation

- Requires: `Python 3.7+`
- Make a python virtual environment: `python -m venv venv`
- Source the environment: `venv\Scripts\activate` (Windows) / `source venv/bin/activate` (macOS, Linux)
- Install the requirements: `pip install -r requirements.txt`

---

### 🔥 Features

- Proxy support for avoiding rate limits
- Multi-threaded account checking
- Real-time checking tracking with console title updates
- Configurable thread count
- Debug mode for troubleshooting
- Proxy/Proxyless mode support
- Automatic token handling
- Detailed logging system
- Account data saving (email:phone format)
- Full account capture with region and country details
- Captcha solving support (NextCaptcha, Capsolver)

---

### 📝 Usage

1. **Configuration**:
   Edit `input/config.toml`:

   ```toml
   [captcha]
   service = "nextcaptcha"  # or "capsolver"
   api_key = "your_api_key"

   [dev]
   Debug = false
   Proxyless = false
   Threads = 1
   MaxRetries = 3
   ```

2. **Proxy Setup** (Optional):

   - Add proxies to `input/proxies.txt` (one per line)
   - Format: `ip:port` or `user:pass@ip:port`

3. **Running the script**:

   ```bash
   python main.py
   ```

4. **Output**:
   - Checked accounts are saved to `output/valid.txt` (email:phone)
   - Invalid accounts saved to `output/invalid.txt`
   - Errors recorded in `output/error.txt`

---

### 📹 Preview

![Preview](https://i.imgur.com/c7yeYrQ.gif)

---

### ❗ Disclaimers

- This project is for educational purposes only
- The author is not responsible for any misuse of this tool
- Use responsibly and in accordance with Crypto.com's terms of service

---

### 📜 ChangeLog

```diff
v0.0.2 ⋮ 11/20/2025
+ Added captcha solving support (NextCaptcha, Capsolver)

v0.0.1 ⋮ 10/21/2025
! Initial release with proxy support and multi-threading
```

<p align="center">
  <img src="https://img.shields.io/github/license/sexfrance/Crypto-Account-Checker.svg?style=for-the-badge&labelColor=black&color=f429ff&logo=IOTA"/>
  <img src="https://img.shields.io/github/stars/sexfrance/Crypto-Account-Checker.svg?style=for-the-badge&labelColor=black&color=f429ff&logo=IOTA"/>
  <img src="https://img.shields.io/github/languages/top/sexfrance/Crypto-Account-Checker.svg?style=for-the-badge&labelColor=black&color=f429ff&logo=python"/>
</p>
