"""Application token only; never forwarded across redirects."""
import os,urllib.request
USER_AGENT='osixbay-agora-bridge/1.0 (+https://github.com/Toramo747/osixbay-agora-bridge)'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):return None

def headers(application_token=None):
    # urllib's default "Python-urllib/3.x" is refused with 403 at the Sites edge; name the client instead.
    result={'Content-Type':'application/json','User-Agent':USER_AGENT}
    if application_token:result['Authorization']='Bearer '+application_token
    return result

def open_request(request,timeout=30):
    return urllib.request.build_opener(NoRedirect).open(request,timeout=timeout)
