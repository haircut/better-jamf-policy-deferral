# Better Jamf Policy Deferral

Sometimes, with Jamf Pro, you need to give your users the option to delay the
execution of a policy until a more convenient time. Typically, this policy might
involve a reboot or some system change that would interrupt a user and present an
annoyance during their work day.

The JSS provides built-in policy deferral options under the "User Interaction"
tab in a policy's configuration (see the docs on "[User Interaction in JSS v9.9x](http://docs.jamf.com/9.9/casper-suite/administrator-guide/User_Interaction.html)).

In use, it looks like this:

![JSS Policy Deferral](https://haircut.keybase.pub/github/better-jamf-policy-deferral/management-task.png)

Maybe your users understand what a "management task" is or can somehow divine
what "id:264" might do to their Mac, or why they might choose a time to start
the task. **Mine cannot**. No options are available to customize the verbiage
or presentation. 

Further, you must specify a hard deadline date by which the policy must run; 
there's no way to specify a "floating" deadline. If a computer falls into the 
scope of a deferral-enabled policy _after_ the deferral deadline, the user is
never presented the choice to delay execution.

Long story short, the built-in deferral is inflexible.

Enter Better Jamf Policy Deferral.

![Better Jamf Policy Deferral](https://haircut.keybase.pub/github/better-jamf-policy-deferral/better-policy-deferment.gif)

## A Word on the Philosophy Behind Deferrals

Why do you want to allow a policy's action(s) to be postponed?

The only acceptable answer is "because those actions present a burdensome
interruption for the user, but are required."

Some examples are:

- A policy that requires your user to reboot their Mac, such as updating the 
  operating system or installing an important reboot-required package.
- To enable FileVault disk encryption.

You should _not_ bloat the user's experience by presenting them the option to 
delay every management action you perform. That's an illusion of choice. Instead,
design your management strategy to be as non-invasive as possible, reserving
policy deferrals for very, very few situations.

Limit yourself to only a couple policies with deferrals enabled. Do not set every
policy to allow deferral because it looks – on the surface – to provide your users
with "control" or autonomy.

## How It Works

Better Jamf Policy Deferral (BJPD) is a Python script that uses the built-in `jamfHelper`
tool to present your user a customizable GUI allowing them to postpone execution
of a policy to a more convenient time.

Behind the scenes, BJPD writes an on-the-fly LaunchDaemon configured to call a
custom policy trigger at the time selected by the user.

## Using Better Jamf Policy Deferral

To better illustrate the workflow, this guide explains requiring a user to install
all available Software Updates.

### Setting Up the Script

1. Customize `better-jamf-policy-deferral.py`, modifying the variables as you
   require for your environment. Variables are well-commented so I won't rehash
   them here. 
2. Add `better-jamf-policy-deferral.py` to your JSS under Settings > Computer 
   Management > Scripts. The script should have a Priority of "Before." Set the
   Parameter Label for Parameter 4 to "Mode (prompt or cleanup).
   Configure the Parameter Label for Parameter 5 as "LaunchDaemon Label." Set 
   the Parameter Label for Parameter 6 to "Jamf Trigger." Set the Parameter Label
   7 to "OS Updates (yes or no)". These optional parameters will allow you to override
   the defaults you set in the script at
   runtime.

### Creating Policies

BJPD requires two separate policies. A "prompt" policy presents the GUI and handles
creating a LaunchDaemon to execute your desired actions at a later time. An
"execution" policy actually executes your actions, then cleans up after itself.

### Execution Policy

1. Create a new Policy with a sensible name. Here, we'll use "Install All Software
   Updates."
2. Set the appropriate options like "Site" and "Category" in the **General** payload
   of the policy.
3. Set a Custom Trigger and make note of this value. We'll use "execute_install_software_updates".
   This should match the name value of the `LD_JAMF_TRIGGER` variable you set in
   `better-jamf-policy-deferral.py` (or that you specify as a parameter value in
   your "prompt" policy).
4. Add a "Scripts" payload and configure the `better-jamf-policy-deferral.py`
   script, set to run "After" policy actions. Set Parameter 4 – the "Mode" 
   parameter – to "cleanup". If you've used a custom LaunchDaemon
   label be sure to pass that value as parameter 5 of the script.
5. Configure other policy payloads to perform whatever actions you require. For
   our example, we'll add the Software Updates payload set to install all 
   available Software Updates. 


### Prompt Policy

1. Create a new Policy and give it an appropriate name. I prefix mine with "Prompt", 
   i.e. "Prompt to Install Software Updates"
2. Set the appropriate options like "Site" and "Category" in the **General** payload
   of the policy. I set the Frequency to "Ongoing" to ensure the deferral GUI is
   shown to all computers that fall into the scope of the policies. The Trigger
   should be set to "recurring check-in."
3. Add a "Scripts" payload and select the `better-jamf-policy-deferral.py` script.
   Set the script to run "Before" other policy items, and configure the parameters
   to your needs. The default "Mode" is "prompt" but you can set it here for
   completeness. Set Parameter 7 - the "OS Update" parameter - to "yes" if you want
   the script to confirm OS updates are still needed before prompting the user,
   default is "no". 
4. Set an appropriate scope. You should be using Smart Groups to determine the 
   scope of computers that must run your "execution policy" and that same Smart
   Group would be an appropriate scope here. For our example "Software Updates"
   policy, a Smart Group with criteria of "Number of Available Updates > 0" 
   might be appropriate.

## Notes and Considerations

### BJPD Always Writes a LaunchDaemon

Even if your user chooses to start the policy "now," BJPD will still write a 
LaunchDaemon. In this case, the LaunchDaemon is written with the `RunAtLoad`
key instead of a future-dated `StartCalendarInterval` key. This ensures the
"execution policy" called by the custom trigger is properly queued up, and the
"prompt policy" can complete its execution.

### Blocking Apps
The BJPD workflow allows you to specify a list of "blocking apps" – a la Munki – 
that, if running, will cause the process to exit silently.

This is useful for...not angering your users. For instance, if a professor or
sales rep is doing a Keynote presentation, you don't want to interrupt by 
throwing your GUI on screen.

App names listed in the `BLOCKING_APPS` list in `better-jamf-policy-deferral.py`
will be checked to see if they're running _prior_ to any GUI elements appearing
on screen.

The default list contains the two most common slide presentation apps:

`BLOCKING_APPS = ['Keynote', 'Microsoft PowerPoint']`

Edit the list to remove apps, or add apps that should additionally halt the
display of GUI elements.

Be sure to test any new blocking apps you add to ensure they work as expected.

Note: This is a "rough" check that cannot detect if, for instance, Keynote is in
full-screen presentation mode vs. simply open and running. A user could indefinitely
delay execution of the policy if they leave a blocking app open all the time.
In my environment, I'd rather be safe than receive the angry phone call. If you
know a better way, _fix it and send a pull request!_

### Policy Scope and Frequency

For deferral "Prompt" policies, I set the policy frequency to "Ongoing." This
_will_ cause the script policy to execute multiple times if a user chooses to 
defer it past the next recurring check-in. BJPD does, however, check for the
existence of a deferral LaunchDaemon on the client prior to displaying any GUI
elements, so the user **will not see the GUI multiple times**.

## Conclusion

If you have questions, shoot me a message @haircut on the [MacAdmins Slack](https://macadmins.slack.com)
team. I'm happy to help :hamburger:
