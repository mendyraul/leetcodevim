using json = nlohmann::json;
template<class T> struct is_vector : false_type {};
template<class T, class A> struct is_vector<vector<T,A>> : true_type {};
template<class T> T decode_arg(const json& j) {
    if constexpr(is_vector<T>::value) {
        T values; for(auto& v:j) values.push_back(decode_arg<typename T::value_type>(v)); return values;
    } else return j.get<T>();
}
template<> char decode_arg<char>(const json& j) {
    auto s=j.get<string>(); if(s.size()!=1) throw runtime_error("Expected one character."); return s[0];
}
template<> ListNode* decode_arg<ListNode*>(const json& j) {
    auto head = new ListNode(); auto p = head;
    if (!j.is_null()) for (auto& v : j) { p->next = new ListNode(v.get<int>()); p = p->next; }
    return head->next;
}
template<> TreeNode* decode_arg<TreeNode*>(const json& j) {
    if (j.is_null() || j.empty() || j[0].is_null()) return nullptr;
    auto root = new TreeNode(j[0].get<int>()); queue<TreeNode*> q; q.push(root); size_t i=1;
    while (!q.empty() && i<j.size()) {
        auto p=q.front(); q.pop();
        if (!j[i].is_null()) { p->left=new TreeNode(j[i].get<int>()); q.push(p->left); } ++i;
        if (i<j.size() && !j[i].is_null()) { p->right=new TreeNode(j[i].get<int>()); q.push(p->right); } ++i;
    } return root;
}
template<class T> json encode_result(const T& value) { return json(value); }
inline json encode_result(ListNode* p) {
    json out=json::array(); set<ListNode*> seen;
    while(p) { if (!seen.insert(p).second) throw runtime_error("Cyclic list requires remote judging.");
        out.push_back(p->val); p=p->next; } return out;
}
inline json encode_result(TreeNode* p) {
    json out=json::array(); queue<TreeNode*> q; if(p) q.push(p);
    while(!q.empty()) { auto n=q.front(); q.pop(); if(!n) out.push_back(nullptr);
        else { out.push_back(n->val); q.push(n->left); q.push(n->right); } }
    while(!out.empty() && out.back().is_null()) out.erase(out.size()-1); return out;
}
inline json encode_result(char value) { return string(1,value); }
template<class T> json encode_result(const vector<T>& values) {
    json out=json::array();
    for(size_t i=0;i<values.size();++i) out.push_back(encode_result(static_cast<T>(values[i])));
    return out;
}
struct LimitBuffer : stringbuf {
    streamsize xsputn(const char* s, streamsize n) override {
        if(n + (pptr() ? pptr()-pbase() : 0) > 512*1024) throw runtime_error("Output limit exceeded.");
        return stringbuf::xsputn(s,n);
    }
    int_type overflow(int_type ch) override {
        if(pptr() && pptr()-pbase() >= 512*1024) throw runtime_error("Output limit exceeded.");
        return stringbuf::overflow(ch);
    }
};
struct Capture {
    LimitBuffer buffer;
    streambuf* rdbuf() { return &buffer; }
    string str() { return buffer.str(); }
};
template<class R, class C, class... A, size_t... I>
json invoke_case(C& instance, R(C::*fn)(A...), const json& input, index_sequence<I...>, bool in_place) {
    tuple<decay_t<A>...> args{decode_arg<decay_t<A>>(input.at(I))...};
    if constexpr(is_void_v<R>) {
        apply([&](auto&... a){ (instance.*fn)(a...); },args);
        if constexpr(sizeof...(A)>0) { if(in_place) return encode_result(get<0>(args)); }
        return nullptr;
    } else return encode_result(apply([&](auto&... a){ return (instance.*fn)(a...); },args));
}
template<class R,class C,class... A>
json invoke_on(C& obj, R(C::*fn)(A...), const json& args, bool inplace=false) {
    return invoke_case(obj,fn,args,index_sequence_for<A...>{},inplace);
}
template<class R,class C,class... A> int run(R(C::*fn)(A...)) {
    json results=json::array();
    try {
        json payload; cin >> payload;
        for(auto& c:payload.at("cases")) {
            Capture capture; auto old=cout.rdbuf(capture.rdbuf()); cout.exceptions(ios::badbit); json actual;
            try { C obj; actual=invoke_on(obj,fn,c.at("args"),c.value("in_place",false)); }
            catch(...) { cout.rdbuf(old); throw; }
            cout.rdbuf(old); results.push_back({{"actual",actual},{"stdout",capture.str()}});
        } cout << json{{"results",results}}.dump();
    } catch(const exception& e) { cout << json{{"error",e.what()}}.dump(); }
    return 0;
}
