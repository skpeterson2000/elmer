/* The drop: where an ELMER unit's reports land, with nothing of the operator's
 * on them and no credential on any unit.
 *
 * This is a Google Apps Script web app. Deployed from the project owner's own
 * Google account, it gives one public URL that takes a POST and does with the
 * report whatever this script says: mails it to the owner, files it in a
 * GitHub folder, or both. Every credential for that lives in the script's own
 * properties, on Google's side; the units know only the URL, and the URL can
 * only put things in.
 *
 * ONE-TIME SETUP (about five minutes)
 *
 *   1. script.google.com -> New project. Replace the contents of Code.gs with
 *      this file. Name the project "ELMER drop".
 *   2. Deploy -> New deployment -> type: Web app.
 *        Execute as:      Me
 *        Who has access:  Anyone
 *      Authorise it when asked (it wants to send mail as you). Copy the URL
 *      it gives you - it ends in /exec.
 *   3. Put that URL in elmer/drop.py as URL, and push. Every unit on that
 *      build now has a way home with nothing to set up.
 *
 *   Reports arrive in the inbox of the account that deployed it. To send
 *   them somewhere else, Project Settings -> Script Properties -> add
 *   MAIL_TO. To also file each one in a GitHub repository, add:
 *        GITHUB_REPO   owner/name        e.g. skpeterson2000/elmer-reports
 *        GITHUB_TOKEN  a fine-grained personal access token with
 *                      Contents: read and write on that one repository
 *   Reports then land as reports/YYYY-MM-DD/HHMMSS-<unit>-<kind>.txt, one
 *   commit each, with the subject as the commit message. The token is never
 *   in the ELMER repository and never on a unit; GitHub's secret scanning
 *   would revoke it there within the hour, and until it did anyone could
 *   write with it. Here it is a script property, readable by the owner alone.
 *
 *   After editing this script: Deploy -> Manage deployments -> edit -> new
 *   version. The URL stays the same.
 *
 * WHAT IT ACCEPTS
 *
 *   A JSON body with tag "ELMER" - anything else is refused - a subject, a
 *   body of at most MOST characters, a kind, and a four-character unit mark
 *   (a hash of the machine id, not its name) for the file name. That is not
 *   security; the address is public and the worst anyone can do with it is
 *   send junk. It is a filter, so the junk has to be trying.
 */

var TAG = 'ELMER';
var SUBJECT_TAG = '[ELMER]';
var MOST = 400000;

function doPost(e) {
  var data;
  try {
    data = JSON.parse((e && e.postData && e.postData.contents) || '');
  } catch (err) {
    return say({ok: false, detail: 'not JSON'});
  }
  if (!data || data.tag !== TAG) {
    return say({ok: false, detail: 'not an ELMER report'});
  }
  var body = String(data.body || '');
  if (!body.trim()) return say({ok: false, detail: 'empty report'});
  if (body.length > MOST) return say({ok: false, detail: 'too long: ' + body.length});

  var subject = String(data.subject || 'report').replace(/[\r\n]+/g, ' ').slice(0, 120);
  if (subject.indexOf(SUBJECT_TAG) !== 0) subject = SUBJECT_TAG + ' ' + subject;
  var kind = clean(data.kind, 'report');
  var unit = clean(data.unit, 'unit');
  var props = PropertiesService.getScriptProperties();
  var out = {ok: true};

  // Mail: to the address in MAIL_TO, or to whoever deployed this.
  var to = props.getProperty('MAIL_TO') || Session.getEffectiveUser().getEmail();
  if (to) {
    try {
      MailApp.sendEmail({to: to, subject: subject, body: body, name: 'ELMER drop'});
      out.mailed = to;
    } catch (err) {
      out.mail_error = String(err);
    }
  }

  // GitHub: one file per report, in a folder by day, one commit each.
  var repo = props.getProperty('GITHUB_REPO');
  var token = props.getProperty('GITHUB_TOKEN');
  if (repo && token) {
    var when = Utilities.formatDate(new Date(), 'UTC', "yyyy-MM-dd'/'HHmmss");
    var path = 'reports/' + when + '-' + unit + '-' + kind + '.txt';
    try {
      var resp = UrlFetchApp.fetch(
        'https://api.github.com/repos/' + repo + '/contents/' + path, {
          method: 'put',
          contentType: 'application/json',
          headers: {
            'Authorization': 'Bearer ' + token,
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28'
          },
          payload: JSON.stringify({
            message: subject,
            content: Utilities.base64Encode(body, Utilities.Charset.UTF_8)
          }),
          muteHttpExceptions: true
        });
      var code = resp.getResponseCode();
      if (code === 201) out.github = path;
      else out.github_error = 'GitHub answered ' + code;
    } catch (err) {
      out.github_error = String(err);
    }
  }

  if (!out.mailed && !out.github) {
    out.ok = false;
    out.detail = out.mail_error || out.github_error || 'nowhere to put it - set MAIL_TO or GITHUB_REPO';
  }
  return say(out);
}

/* Opening the URL in a browser says what this is, so a deployment can be
 * checked without sending anything. */
function doGet() {
  var props = PropertiesService.getScriptProperties();
  return say({
    ok: true,
    what: 'ELMER report drop',
    takes: 'POST, JSON, tag "' + TAG + '"',
    mails: !!(props.getProperty('MAIL_TO') || Session.getEffectiveUser().getEmail()),
    files: !!(props.getProperty('GITHUB_REPO') && props.getProperty('GITHUB_TOKEN'))
  });
}

function clean(value, fallback) {
  var s = String(value || '').replace(/[^A-Za-z0-9_-]/g, '').slice(0, 40);
  return s || fallback;
}

function say(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
