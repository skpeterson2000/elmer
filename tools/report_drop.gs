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

/* HOW MANY
 *
 * The address is public, so something has to say how much it will take.
 *
 *   PER_UNIT_HOUR  6   One unit mark in any clock hour. Somebody chasing a
 *                      fault writes, sends, restarts and sends again; three
 *                      or four in an hour is a person, six leaves room for
 *                      the test message and a resend, and past that it is a
 *                      loop - a unit stuck sending the same report - or
 *                      somebody who has found the URL.
 *   ALL_HOUR      30   Every unit together. The mark is the sender's own
 *                      word, so a sender can change it each time; this is
 *                      the limit that holds whatever it claims to be. A
 *                      hamfest hall of twenty units reporting in one hour
 *                      is already a very bad hour.
 *   ALL_DAY       80   MailApp on an ordinary Google account sends about a
 *                      hundred mails a day, and the owner's own mail comes
 *                      out of the same quota. Past it every report fails to
 *                      mail anyway; stopping at 80 leaves the owner room.
 *
 * A report over a limit is refused with ok: false and a detail that says
 * which limit and when it resets. The unit keeps the report - it was
 * written to disk before it was sent - and its page offers it by hand.
 * The hour's counts live in the script cache, which may forget early: that
 * limit can let a few more through, never fewer, which is the right way for
 * a filter to fail. The day's count is a script property (DROP_DAY_COUNT),
 * because the cache keeps nothing past six hours.
 */
var PER_UNIT_HOUR = 6;
var ALL_HOUR = 30;
var ALL_DAY = 80;

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
  var over = overLimit(unit);
  if (over) return say({ok: false, detail: over});
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
    files: !!(props.getProperty('GITHUB_REPO') && props.getProperty('GITHUB_TOKEN')),
    // Which limits this deployment holds - and so whether the version with
    // them in it is the one deployed.
    limits: {per_unit_hour: PER_UNIT_HOUR, all_hour: ALL_HOUR, all_day: ALL_DAY}
  });
}

/* null if this report may go, or the sentence saying why it may not. Counted
 * under a lock, because two reports in the same second would each read the
 * count before either wrote it back. A lock that cannot be had in five
 * seconds lets the report through rather than refusing it: a busy drop is
 * not a reason to lose somebody's report. */
function overLimit(unit) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) return null;
  try {
    var cache = CacheService.getScriptCache();
    var now = new Date();
    var hour = Utilities.formatDate(now, 'UTC', 'yyyyMMddHH');
    var day = Utilities.formatDate(now, 'UTC', 'yyyyMMdd');
    var keys = {mine: 'n:h:' + hour + ':' + unit, hour: 'n:h:' + hour};
    var got = cache.getAll([keys.mine, keys.hour]);
    var mine = Number(got[keys.mine] || 0);
    var inHour = Number(got[keys.hour] || 0);
    // The day's count outlives the cache, which keeps nothing past six
    // hours: it is a script property, "yyyyMMdd:count", one write a report.
    var props = PropertiesService.getScriptProperties();
    var stamp = String(props.getProperty('DROP_DAY_COUNT') || '').split(':');
    var inDay = stamp[0] === day ? Number(stamp[1] || 0) : 0;
    if (mine >= PER_UNIT_HOUR) {
      return 'this unit has sent ' + mine + ' reports this hour, the most one unit may; ' +
             'it is kept on the unit - send it again after the hour (UTC)';
    }
    if (inHour >= ALL_HOUR) {
      return 'the drop has taken ' + inHour + ' reports this hour from every unit together; ' +
             'it is kept on the unit - send it again after the hour (UTC)';
    }
    if (inDay >= ALL_DAY) {
      return 'the drop has taken ' + inDay + ' reports today; it is kept on the unit - ' +
             'send it again tomorrow (UTC), or by hand';
    }
    cache.put(keys.mine, String(mine + 1), 3700);
    cache.put(keys.hour, String(inHour + 1), 3700);
    props.setProperty('DROP_DAY_COUNT', day + ':' + (inDay + 1));
    return null;
  } finally {
    lock.releaseLock();
  }
}

function clean(value, fallback) {
  var s = String(value || '').replace(/[^A-Za-z0-9_-]/g, '').slice(0, 40);
  return s || fallback;
}

function say(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
