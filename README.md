# worst-password-manager
Want to store your private data, passwords, in the goofiest way possible? This is the right repo for you shit!

# a.k.a RONIN PASSWORD MANAGER

*Because remembering passwords is a scam and your brain deserves PTO.*

---

## What is this?

This is a **terminal-based password manager** that:

* Locks your secrets behind math so intense it scares away both hackers and your future self
* Judges your terrible password choices in real time
* Lets you stash random encrypted nonsense like a digital raccoon

Built with:

* `textual` (so it looks fancy in your terminal)
* `cryptography` (so your data isn’t just sitting there naked)
* Vibes (questionable)

---

## Disclaimer (read this or regret it later)

* If you forget your master password:
  **you are done. finished. spiritually bankrupt.**
* There is no “forgot password”
* There is no “admin override”
* There is only you and your poor life choices

---

## Features

### 1. Master Password

You get **one key**. Lose it and your vault becomes modern art.

### 2. Password Vault

* Stores passwords encrypted
* Shows them back to you because apparently you can’t be trusted to remember anything
* No cloud. No sync. Just you and your local chaos

### 3. Password Generator

* Generates strong passwords like:
  `gH#9!xP@2...something you will NEVER remember`
* You *will* forget it immediately
* That’s the point

### 4. Password Strength Checker

Rates your passwords from:

* “cracked before you blink”
* “my grandma guessed this”
* “FORTRESS. NSA is tired.”

### 5. Breach Checker

Uses HaveIBeenPwned API to tell you:

> “Yeah… this password has been leaked 47,000 times. Bold choice.”

### 6. Custom Data Vault

Store literally anything:

* passwords
* notes
* secrets
* grocery lists
* emotional damage

Encrypted. Hidden. Questionable.

---

## THE DASHBOARD! (UX Flow after login)
Its just the screen that appears after you log in. The below widgets are sitting in front of you now:
* **Passwords**: Displays all your random passwords, and poorly thought passwords. Also has a button to add password, which gives you two options:
  - Create your own password, and check its strenght (thats a bold choice aint gonna lie)
  - Generate a random password, of whatever length you want (default is 16)
* **Custom Data**: This widget displays all your custom data
  - You can store _anything_ you want here, and i mean _*anythin*_, from your diary, to your secrets, to your love letter you always wanted to give your crush but will prolly never will, and heck even your man grocery list.
  - A button to add some custom data is present

And the some other buttons:
* **Logout button**: It just logs you out, man
  
* If there are any other things in the UI, its **textual's** fault, not mine. Blame Will McGugan...

## How It Works (for people who like big words)

* PBKDF2 + SHA256 → derives encryption key
* Fernet → symmetric encryption
* SHA3-512 → hashes your master password
* Local JSON files → your entire digital existence

Translation:

> It’s secure enough unless you do something dumb.

---

## Setup

```bash
pip install textual cryptography requests
python ronin.py
```

First run:

* You set a master password
* The app stares into your soul and says “don’t forget this”
* You forget it anyway

---

## Usage

### Start

```bash
python ronin.py
```

### Then:

* Login (or fail repeatedly)
* Add passwords
* Generate passwords
* Question your past decisions

---

## Design Philosophy

* No cloud → because trust issues
* No recovery → because consequences build character
* No hand-holding → because you’re an adult (allegedly)

---

## Known Issues

* You might lock yourself out forever
* You might realize how bad your passwords are
* You might develop trust issues with your own memory

---

## Final Words

This app does not care about:

* your feelings
* your convenience
* your ability to remember things

It only cares about one thing:

> **keeping your secrets locked away like a dramatic anime backstory**

---

## Motto

> “Strong passwords. Weak life decisions.”

---

## Bonus Tip

If your master password is:

```
password123
```

Just uninstall the app.
Start over.
Start life over.

---

## How It Actually Works (Flow + Explanation)

### Flow (high-level, no nonsense)

```
[Start App]
      |
      v
[Master file exists?] ---- no ----> [Setup Screen]
      |                               |
     yes                              v
      |                       [User sets master password]
      v                               |
[Login Screen]                        v
      |                       [Hash + salt saved]
      v                               |
[Enter master password]               v
      |                        [Exit → restart app]
      v
[Verify hash]
      |
   wrong ----> [Insult user] → retry
      |
    correct
      v
[Derive encryption key (PBKDF2)]
      |
      v
[Dashboard]
   |           |
   v           v
[Passwords]  [Custom Data]

Passwords:
  Add → encrypt → store JSON
  View → decrypt → display

Custom Data:
  Add → encrypt → save .enc file
  View → decrypt → display

Extras:
  - Password strength → entropy math
  - Breach check → API call (HIBP)
```

---

### What’s Actually Happening Under the Hood

* Your **master password is never stored directly**
  → It’s hashed with SHA3-512 + salt

* That same password is used to:
  → Derive an encryption key using PBKDF2 (100k iterations, so attackers suffer)

* That key is fed into:
  → Fernet (AES-based symmetric encryption)

* When you save something:
  → Plaintext → encrypted → stored on disk

* When you view something:
  → Encrypted → decrypted → shown to your unworthy eyes

* If the password is wrong:
  → Decryption fails → you get nothing → life lesson delivered

---

### In Simple Terms

You:

> type password → get key → lock/unlock secrets

Program:

> “I will protect this with cryptography and also emotionally damage you along the way.”

---

good luck 👍


## LICENSE
Do whatever you want with it.


## Very very very very important note:
- This is a damn learning **project**, not a real security **'product'**. Heck even I am not using this since i dont trust me.
- So you know, just dont use it much, but if you do use it, its on you if something bad happens... ; )
