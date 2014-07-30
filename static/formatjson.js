function formatJsonContent(idEditor){
  var editor = ace.edit(idEditor);
  var content = editor.getSession().getValue().trim().replace(/\n/g, '');
  //console.log(content);
  try {
    content = JSON.stringify(JSON.parse(content), null, '\t');
    editor.getSession().setValue(content);
  } catch (e) {
    console.log(e);
  }
}
