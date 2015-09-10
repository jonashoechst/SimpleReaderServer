function sendMessage(form, text) {
    var message = prompt(text);
    element = document.createElement('input');
    element.setAttribute('name', 'message_content');
    element.setAttribute('type', 'hidden');
    element.setAttribute('value', message);
    form.appendChild(element);
    return ( message != null && message != '' );
}