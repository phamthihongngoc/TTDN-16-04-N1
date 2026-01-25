odoo.define('ai_integration.chat_widget', function (require) {
'use strict';

var AbstractAction = require('web.AbstractAction');
var core = require('web.core');
var ajax = require('web.ajax');
var session = require('web.session');
var QWeb = core.qweb;
var _t = core._t;

/**
 * AI Chat Widget - Client Action
 * Hiển thị giao diện chat với AI Assistant
 */
var AIChatWidget = AbstractAction.extend({
    hasControlPanel: false,
    contentTemplate: 'ai_integration.ChatFullPage',
    
    events: {
        'click .ai-chat-send': '_onSendMessage',
        'keypress .ai-chat-input': '_onInputKeypress',
        'click .ai-quick-action': '_onQuickAction',
        'click .ai-clear-chat': '_onClearChat',
        'click .ai-new-session': '_onNewSession',
    },

    /**
     * @override
     */
    init: function (parent, action) {
        this._super.apply(this, arguments);
        this.action = action;
        this.sessionId = null;
        this.messages = [];
        this.isLoading = false;
        this.module = action.context && action.context.default_module;
        this.activeModel = action.context && action.context.active_model;
        this.activeResId = action.context && action.context.active_id;
    },

    /**
     * @override
     */
    willStart: function () {
        var self = this;
        return this._super.apply(this, arguments);
    },

    /**
     * @override
     */
    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self._initChat();
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Khởi tạo chat session
     * @private
     */
    _initChat: function () {
        var self = this;
        
        // Create or get existing session
        return this._rpc({
            model: 'ai.chat.session',
            method: 'create_or_get_session',
            args: [{
                module: this.module,
                active_model: this.activeModel,
                active_res_id: this.activeResId,
            }],
        }).then(function (session) {
            self.sessionId = session.id;
            self.messages = session.messages || [];
            self._renderMessages();
            self._focusInput();
        });
    },

    /**
     * Gửi tin nhắn đến AI
     * @private
     * @param {string} message
     */
    _sendMessage: function (message) {
        var self = this;
        
        if (!message || !message.trim()) {
            return Promise.resolve();
        }

        // Add user message to UI
        this._addMessage({
            role: 'user',
            content: message,
            timestamp: new Date().toISOString(),
        });

        this.isLoading = true;
        this._setLoading(true);

        return this._rpc({
            model: 'ai.chat.orchestrator',
            method: 'send_message',
            args: [this.sessionId, message],
        }).then(function (response) {
            self.isLoading = false;
            self._setLoading(false);

            if (response.success) {
                self._addMessage({
                    role: 'assistant',
                    content: response.message || response.data || 'Không có phản hồi',
                    timestamp: new Date().toISOString(),
                });
            } else {
                self._showError(response.error || 'Có lỗi xảy ra');
            }
        }).catch(function (error) {
            self.isLoading = false;
            self._setLoading(false);
            self._showError('Lỗi kết nối: ' + (error.message || error.data || error));
        });
    },

    /**
     * Thêm tin nhắn vào UI
     * @private
     * @param {Object} message
     */
    _addMessage: function (message) {
        this.messages.push(message);
        this._renderMessages();
        this._scrollToBottom();
    },

    /**
     * Render lại danh sách tin nhắn
     * @private
     */
    _renderMessages: function () {
        var self = this;
        var $messagesContainer = this.$('.ai-chat-messages');
        if (!$messagesContainer.length) {
            return;
        }

        $messagesContainer.empty();

        // Group messages into Q&A pairs
        var conversations = [];
        var currentConversation = null;
        
        this.messages.forEach(function (msg) {
            if (msg.role === 'user') {
                // Start new conversation with user question
                currentConversation = {
                    question: msg,
                    answer: null
                };
                conversations.push(currentConversation);
            } else if (msg.role === 'assistant' && currentConversation) {
                // Add assistant answer to current conversation
                currentConversation.answer = msg;
            }
        });

        // Render each conversation as a card with Q&A sections
        conversations.forEach(function (conv) {
            var $card = $('<div>').addClass('ai-conversation-card');
            
            // Question section
            var $questionSection = $('<div>').addClass('ai-question-section');
            var $questionHeader = $('<div>').addClass('ai-section-header')
                .append($('<i>').addClass('fa fa-user-circle'))
                .append($('<span>').text('Câu hỏi của bạn'));
            var $questionContent = $('<div>').addClass('ai-section-content')
                .html(self._formatMessage(conv.question.content));
            var $questionTime = $('<div>').addClass('ai-section-time')
                .text(self._formatTime(conv.question.timestamp));
            
            $questionSection.append($questionHeader, $questionContent, $questionTime);
            
            // Answer section (if exists)
            if (conv.answer) {
                var $answerSection = $('<div>').addClass('ai-answer-section');
                var $answerHeader = $('<div>').addClass('ai-section-header')
                    .append($('<i>').addClass('fa fa-robot'))
                    .append($('<span>').text('Trả lời của AI'));
                var $answerContent = $('<div>').addClass('ai-section-content')
                    .html(self._formatMessage(conv.answer.content));
                var $answerTime = $('<div>').addClass('ai-section-time')
                    .text(self._formatTime(conv.answer.timestamp));
                
                $answerSection.append($answerHeader, $answerContent, $answerTime);
                $card.append($questionSection, $answerSection);
            } else {
                $card.append($questionSection);
            }
            
            $messagesContainer.append($card);
        });
        
        self._scrollToBottom();
    },

    /**
     * Format nội dung tin nhắn (markdown -> HTML)
     * @private
     * @param {string} content
     * @returns {string}
     */
    _formatMessage: function (content) {
        if (!content) return '';
        
        // Simple markdown formatting
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br/>');
    },

    /**
     * Format timestamp
     * @private
     * @param {string} timestamp
     * @returns {string}
     */
    _formatTime: function (timestamp) {
        if (!timestamp) return '';
        var date = new Date(timestamp);
        return date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    },

    /**
     * Scroll xuống cuối danh sách tin nhắn
     * @private
     */
    _scrollToBottom: function () {
        var $container = this.$('.ai-chat-messages');
        if ($container.length) {
            $container.scrollTop($container[0].scrollHeight);
        }
    },

    /**
     * Focus vào input
     * @private
     */
    _focusInput: function () {
        this.$('.ai-chat-input').focus();
    },

    /**
     * Hiển thị/ẩn loading
     * @private
     * @param {boolean} loading
     */
    _setLoading: function (loading) {
        this.$('.ai-chat-send').prop('disabled', loading);
        this.$('.ai-chat-input').prop('disabled', loading);
        
        if (loading) {
            this.$('.ai-chat-loading').show();
        } else {
            this.$('.ai-chat-loading').hide();
        }
    },

    /**
     * Hiển thị lỗi
     * @private
     * @param {string} message
     */
    _showError: function (message) {
        this.displayNotification({
            title: _t('Lỗi'),
            message: message,
            type: 'danger',
        });
    },

    /**
     * Xóa lịch sử chat
     * @private
     */
    _clearChat: function () {
        var self = this;
        
        return this._rpc({
            model: 'ai.chat.session',
            method: 'clear_session',
            args: [this.sessionId],
        }).then(function () {
            self.messages = [];
            self._renderMessages();
            self.displayNotification({
                title: _t('Thành công'),
                message: _t('Đã xóa lịch sử chat'),
                type: 'success',
            });
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Event} ev
     */
    _onSendMessage: function (ev) {
        ev.preventDefault();
        var $input = this.$('.ai-chat-input');
        var message = $input.val().trim();
        
        if (message) {
            this._sendMessage(message);
            $input.val('');
        }
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onInputKeypress: function (ev) {
        if (ev.which === 13 && !ev.shiftKey) {
            ev.preventDefault();
            this._onSendMessage(ev);
        }
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onQuickAction: function (ev) {
        ev.preventDefault();
        var message = $(ev.currentTarget).data('prompt');
        if (message) {
            this.$('.ai-chat-input').val(message);
            this._onSendMessage(ev);
        }
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onClearChat: function (ev) {
        ev.preventDefault();
        var self = this;
        
        if (confirm(_t('Bạn có chắc muốn xóa toàn bộ lịch sử chat?'))) {
            self._clearChat();
        }
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onNewSession: function (ev) {
        ev.preventDefault();
        this.sessionId = null;
        this.messages = [];
        this._renderMessages();
        this._initChat();
    },
});

core.action_registry.add('ai_chat_widget', AIChatWidget);

return AIChatWidget;

});

