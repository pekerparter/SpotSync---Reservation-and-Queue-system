const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../SpotSync/static/accounts/js/escape_html.js'), 'utf8'), context);

test('editable names, emails, and service options remain text in HTML', () => {
    const escaped = context.spotSyncEscapeHtml('<img src=x onerror="alert(1)">');
    assert.equal(escaped, '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
    assert.ok(!escaped.includes('<'));
});

test('quotes and ampersands cannot escape a quoted attribute', () => {
    assert.equal(context.spotSyncEscapeHtml('" autofocus onfocus=\'run()\' &'),
        '&quot; autofocus onfocus=&#39;run()&#39; &amp;');
});

test('ordinary labels, whitespace, and Unicode retain their meaning', () => {
    assert.equal(context.spotSyncEscapeHtml('Court A — 10:00'), 'Court A — 10:00');
});
