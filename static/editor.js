// Hook up ACE editor to all textareas with data-editor attribute
$(function () {
    $('textarea[data-editor]').each(function () {
        var textarea = $(this);

        var mode = textarea.data('editor');

        var editDiv = $('<div>', {
            position: 'absolute',
            width: textarea.width(),
            height: textarea.height(),
            'class': textarea.attr('class')
        })

        editDiv.insertBefore(textarea);

        textarea.css('visibility', 'hidden').css('width', '0').css('height', '0');

        var editor = ace.edit(editDiv[0]);
        // https://github.com/ajaxorg/ace/tree/master/lib/ace/theme
        editor.setTheme('ace/theme/tomorrow');
        var modelist = ace.require('ace/ext/modelist');
        var content = textarea.val();
        if (modelist.modesByName[mode] != undefined) {
            editor.getSession().setMode(modelist.modesByName[mode].mode);
            if (content.length != 0 && mode == "json") {
                try{ 
                    content = JSON.stringify(JSON.parse(content), null, '\t');
                } catch (e) {
                    console.log('unable to parse json content');
                }
            }
        }

        editor.getSession().setValue(content);

        // copy back to textarea on form submit...
        textarea.closest('form').submit(function () {
            textarea.val(editor.getSession().getValue());
        })

        editDiv.resizable();
        
    });
});
