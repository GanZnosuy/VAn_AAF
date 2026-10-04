JS_EXTRACTOR_SCRIPT = """() => {
    function mmlToText(node) {
        if (!node) return '';
        if (node.nodeType === Node.TEXT_NODE) return node.textContent.trim();
        const tag = node.tagName.toLowerCase();
        const children = Array.from(node.childNodes);
        if (tag === 'msup') return mmlToText(children[0]) + '^' + mmlToText(children[1]);
        if (tag === 'msub') return mmlToText(children[0]) + '_' + mmlToText(children[1]);
        if (tag === 'msubsup') return mmlToText(children[0]) + '_' + mmlToText(children[1]) + '^' + mmlToText(children[2]);
        if (tag === 'mfrac') return '(' + mmlToText(children[0]) + ')/(' + mmlToText(children[1]) + ')';
        if (tag === 'msqrt') return 'sqrt(' + children.map(mmlToText).join('') + ')';
        if (tag === 'mover') return 'vec(' + mmlToText(children[0]) + ')';
        return children.map(mmlToText).join('');
    }

    function getCleanText(el) {
        if (!el) return '';
        const clone = el.cloneNode(true);
        clone.querySelectorAll('mjx-container').forEach(c => {
            const mml = c.querySelector('math');
            if (mml) {
                c.replaceWith(document.createTextNode(' ' + mmlToText(mml) + ' '));
            } else {
                c.replaceWith(document.createTextNode(' ' + c.innerText.replace(/\\s+/g, '') + ' '));
            }
        });
        clone.querySelectorAll('img').forEach(img => {
            img.replaceWith(document.createTextNode(' [Hình: ' + (img.alt || img.src) + '] '));
        });
        return clone.innerText.replace(/\\s+/g, ' ').trim();
    }

    const qName = document.querySelector('.question-name') || document.querySelector('.question-title') || document.querySelector('.step-content');
    const questionText = getCleanText(qName);
    const opts = Array.from(document.querySelectorAll('.question-option')).map(o => getCleanText(o));
    
    // Tìm các câu khẳng định Đúng/Sai
    const statements = [];
    for (const el of document.querySelectorAll('p, div, li, tr')) {
        const t = getCleanText(el);
        if (/^[a-d]\\)/.test(t) && t.length < 350) {
            statements.push(t.replace(/ĐúngSai/g, '').trim());
        }
    }
    
    // Loại trừ trùng lặp
    const uniqueStmts = [];
    for (const s of statements) {
        if (!uniqueStmts.some(u => u.startsWith(s.substring(0, 5)))) {
            uniqueStmts.push(s);
        }
    }

    const hasInput = !!document.querySelector("input[id^='mathplay-answer'], .step-content input[type='text'], input.can-resize-second");
    const labels = Array.from(document.querySelectorAll('label')).filter(l => {
        const t = l.innerText ? l.innerText.trim() : '';
        return t === 'Đúng' || t === 'Sai';
    });
    const hasTrueFalse = labels.length >= 8;

    return {
        question: questionText,
        options: opts,
        statements: uniqueStmts,
        hasInput: hasInput,
        hasTrueFalse: hasTrueFalse,
        numOptions: opts.length
    };
}"""
